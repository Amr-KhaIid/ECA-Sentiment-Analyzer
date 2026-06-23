# data_processing/csv_handler.py
import pandas as pd
import os
from sklearn.metrics import precision_recall_fscore_support

class CSVHandler:
    def __init__(self, pipeline):
        """يستقبل الـ Pipeline الخاص بالتحليل الهجين كمرجع"""
        self.pipeline = pipeline

    def process_batch_file(self, file_path, progress_callback=None, check_stop_callback=None):
        """يقوم بقراءة الملف، تحليله صفا بصف، وإرجاع البيانات للواجهة لعرضها"""
        # 1. قراءة الملف
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        if df.empty:
            raise ValueError("الملف المرفوع فارغ تماماً!")

        # افتراض أن النص موجود في العمود الأول
        text_col = df.columns[0]
        results_list = []
        total_rows = len(df)

        # 2. تحليل الجمل صفاً بصف
        for index, row in df.iterrows():
            #  فحص زرار التوقف (Kill Switch)
            if check_stop_callback and check_stop_callback():
                break

            text = str(row[text_col])
            if pd.isna(text) or not text.strip() or text.lower() == 'nan':
                continue

            # استدعاء المحلل
            res = self.pipeline.analyze(text)
            
            # تجهيز عمود أوزان الذكاء الاصطناعي
            ai_weights = "، ".join([f"{w} ({weight}%)" for w, weight in res.get('top_ai_weights', [])])
            
            # تجهيز عمود الكلمات المؤثرة في القواعد
            rule_words = []
            if res.get('matched_segments'): rule_words.extend(res['matched_segments'])
            if res.get('lexicon_pos_words'): rule_words.extend(res['lexicon_pos_words'])
            if res.get('lexicon_neg_words'): rule_words.extend(res['lexicon_neg_words'])
            rule_words_str = "، ".join(set(rule_words)) if rule_words else "لا يوجد"
            
            # تجهيز القواعد وتحديد المصدر
            rules_str = "، ".join(res.get('triggered_rules', [])) if res.get('triggered_rules') else "لا يوجد"
            
            # تحديد مصدر القرار بدقة للفلاتر والرسم البياني
            decision_source = "الذكاء الاصطناعي"
            if "User Feedback Database" in rules_str:
                decision_source = "السحابة (Feedback)"
            elif rules_str != "لا يوجد" and "Lexicon Conflict" not in rules_str:
                decision_source = "محرك القواعد"

            is_sarcasm = "نعم" if res.get('has_sarcasm') else "لا"

            # 3. بناء القاموس بالأعمدة المطلوبة للواجهة
            results_list.append({
                "النص الأصلي": text,
                "النتيجة النهائية": res.get('final_sentiment', 'غير معروف'),
                "السخرية": is_sarcasm,
                "مصدر القرار": decision_source,
                "القاعدة المفعلة": rules_str,
                "ثقة الذكاء الاصطناعي (%)": res.get('dl_confidence', 0),
                "انتباه AI": ai_weights if ai_weights else "لا يوجد",
                "كلمات القواعد": rule_words_str,
                "قرار AI الأصلي": res.get('dl_original_prediction', 'غير معروف') # مخفي لحساب الـ Metrics
            })

            # تحديث شريط التقدم في الواجهة
            if progress_callback:
                p = int(((index + 1) / total_rows) * 100)
                progress_callback(p)

        # إرجاع الداتا فريم للواجهة عشان تترسم في الجدول (بدل الحفظ الفوري)
        return pd.DataFrame(results_list)

    def filter_dataframe(self, df, source, rule_filter, max_ai_conf, sentiment):
        """تطبيق الفلاتر المتعددة على البيانات المجمعة"""
        if df is None or df.empty:
            return df
            
        filtered = df.copy()
        
        if source != "الكل":
            filtered = filtered[filtered["مصدر القرار"] == source]
            
        if rule_filter != "الكل":
            filtered = filtered[filtered["القاعدة المفعلة"].str.contains(rule_filter, na=False)]
            
        if max_ai_conf < 100:
            filtered = filtered[filtered["ثقة الذكاء الاصطناعي (%)"] <= max_ai_conf]
            
        if sentiment != "الكل":
            filtered = filtered[filtered["النتيجة النهائية"] == sentiment]
            
        return filtered

    def calculate_dashboard_metrics(self, df):
        """حساب كافة إحصائيات لوحة التحكم (Metrics)"""
        if df is None or df.empty:
            return None

        # 1. حساب F1, Precision, Recall 
        y_true = df["النتيجة النهائية"].tolist()
        y_pred = df["قرار AI الأصلي"].tolist()
        
        # تجاهل الأخطاء في حالة عدم وجود كلاسات كافية في العينة
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='weighted', zero_division=0
        )

        # 2. إحصائيات المشاعر (Pie Chart)
        sentiment_counts = df["النتيجة النهائية"].value_counts().to_dict()

        # 3. إحصائيات مصادر القرار (Bar Chart)
        source_counts = df["مصدر القرار"].value_counts().to_dict()

        # 4. إحصائيات أنواع القواعد المستخدمة
        rules_only = df[df["القاعدة المفعلة"] != "لا يوجد"]["القاعدة المفعلة"]
        rule_types_counts = {}
        for rules in rules_only:
            for rule in rules.split("، "):
                clean_rule = rule.split(":")[0].strip() # أخذ اسم القاعدة الرئيسي فقط
                rule_types_counts[clean_rule] = rule_types_counts.get(clean_rule, 0) + 1

        return {
            "total_records": len(df),
            "f1_score": round(f1 * 100, 2),
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "sentiment_counts": sentiment_counts,
            "source_counts": source_counts,
            "rule_types_counts": rule_types_counts
        }

    def process_batch_dataframe(self, df, progress_callback=None, check_stop_callback=None):
        """يستقبل داتا فريم جاهزة (من الجدول في الواجهة) ويحللها"""
        if df.empty:
            raise ValueError("لا توجد بيانات للتحليل!")

        text_col = df.columns[0]
        results_list = []
        total_rows = len(df)

        for index, row in df.iterrows():
            if check_stop_callback and check_stop_callback():
                break

            text = str(row[text_col])
            if pd.isna(text) or not text.strip() or text.lower() == 'nan':
                continue

            # استدعاء المحلل
            res = self.pipeline.analyze(text)
            
            ai_weights = "، ".join([f"{w} ({weight}%)" for w, weight in res.get('top_ai_weights', [])])
            
            rule_words = []
            if res.get('matched_segments'): rule_words.extend(res['matched_segments'])
            if res.get('lexicon_pos_words'): rule_words.extend(res['lexicon_pos_words'])
            if res.get('lexicon_neg_words'): rule_words.extend(res['lexicon_neg_words'])
            rule_words_str = "، ".join(set(rule_words)) if rule_words else "لا يوجد"
            
            rules_str = "، ".join(res.get('triggered_rules', [])) if res.get('triggered_rules') else "لا يوجد"
            
            decision_source = "الذكاء الاصطناعي"
            if "User Feedback Database" in rules_str:
                decision_source = "السحابة (Feedback)"
            elif rules_str != "لا يوجد" and "Lexicon Conflict" not in rules_str:
                decision_source = "محرك القواعد"

            is_sarcasm = "نعم" if res.get('has_sarcasm') else "لا"

            results_list.append({
                "النص الأصلي": text,
                "النتيجة النهائية": res.get('final_sentiment', 'غير معروف'),
                "السخرية": is_sarcasm,
                "مصدر القرار": decision_source,
                "القاعدة المفعلة": rules_str,
                "ثقة الذكاء الاصطناعي (%)": res.get('dl_confidence', 0),
                "انتباه AI": ai_weights if ai_weights else "لا يوجد",
                "كلمات القواعد": rule_words_str,
                "قرار AI الأصلي": res.get('dl_original_prediction', 'غير معروف')
            })

            if progress_callback:
                p = int(((index + 1) / total_rows) * 100)
                progress_callback(p)

        return pd.DataFrame(results_list)

    def export_to_excel(self, df, suggested_path=None):
        """تصدير الداتا فريم إلى ملف إكسيل مع إنشاء المسار لو مش موجود"""
        if df is not None and not df.empty:
            # استخراج المسار الجذري للمشروع
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "reports", "annotated_datasets")
            os.makedirs(output_dir, exist_ok=True) 

            # تحديد مسار الحفظ النهائي
            if suggested_path:
                final_path = suggested_path
            else:
                final_path = os.path.join(output_dir, "Analyzed_Export.xlsx")
                
            # إزالة العمود المخفي قبل التصدير
            export_df = df.drop(columns=["قرار AI الأصلي"], errors='ignore')
            export_df.to_excel(final_path, index=False)
            return True
        return False