# core/hybrid_analyzer.py
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import os

from core.text_cleaner import clean_arabic_text
from core.rules_extractor import RuleFeatureExtractor
from database.cloud_memory import get_all_feedback
# 👈 التعديل 1: استدعاء الـ Wrapper
from core.udpipe_wrapper import UDPipeWrapper 

class HybridPipeline:
    def __init__(self, model_path="models/Active_Model"):
        """تحميل الموديل والقواعد مرة واحدة في الذاكرة لتسريع الأداء"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        abs_model_path = os.path.abspath(model_path)
        
        if not os.path.exists(abs_model_path):
            raise Exception(f"❌ مجلد الموديل غير موجود! يرجى التأكد من وضع ملفات الموديل في: {abs_model_path}")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(abs_model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                abs_model_path,
                attn_implementation="eager"
            ).to(self.device)
            self.model.eval() 
        except Exception as e:
            raise Exception(f"❌ حدث خطأ أثناء قراءة ملفات الموديل من المجلد: {e}")

        self.rule_engine = RuleFeatureExtractor()
        
        # 👈 التعديل 2: تهيئة موديل الـ UDPipe
        self.udpipe = UDPipeWrapper()
        
        self.labels_map = {0: "محايد", 1: "إيجابي", 2: "سلبي"}
        
        self.user_feedback_cache = get_all_feedback()
        print(f"✅ تم تحميل {len(self.user_feedback_cache)} تقييم من السحابة.")

    def analyze(self, raw_text):
        """التحليل الهجين واستخراج أوزان الانتباه (Explainable AI)"""
        
        # 1. الفحص الفوري في قاعدة بيانات المستخدمين (Override)
        if raw_text in self.user_feedback_cache:
            saved_data = self.user_feedback_cache[raw_text]
            sarcasm_flag = saved_data['sarcasm']
            reason = "استرجاع نتيجة من الـ User Feedback Database ☁️"
            if sarcasm_flag:
                reason += " (تم تصنيفها كسخرية)"
                
            return {
                "original_text": raw_text,
                "final_sentiment": saved_data['sentiment'],
                "dl_confidence": 100.0,
                "dl_original_prediction": "تم التجاوز (Overridden)",
                "top_ai_weights": [],
                "has_sarcasm": sarcasm_flag,
                "has_negation": False,
                "triggered_rules": [reason],
                "matched_segments": ["تم السحب من السحابة"],
                "lexicon_conflict": False,
                "lexicon_score": 0,
                "lexicon_pos_words": [],
                "lexicon_neg_words": []
            }

        # 2. التنظيف
        cleaned_text = clean_arabic_text(raw_text)
        if not cleaned_text:
            return {
                "original_text": raw_text,
                "final_sentiment": "فارغ",
                "dl_confidence": 0,
                "dl_original_prediction": "فارغ",
                "top_ai_weights": [],
                "has_sarcasm": False,
                "has_negation": False,
                "triggered_rules": [],
                "matched_segments": [],
                "lexicon_conflict": False,
                "lexicon_score": 0,
                "lexicon_pos_words": [],
                "lexicon_neg_words": []
            }

        # 👈 التعديل 3: استخراج أصل الكلمات (Lemmas)
        lemmatized_text = self.udpipe.get_lemmas(cleaned_text)

        # 3. استخراج القواعد والمقاطع 
        # 👈 التعديل 4: نمرر النص الأصلي والنص المُردد لأصله لمحرك القواعد
        rule_results = self.rule_engine.analyze_rules(raw_text, lemmatized_text)

        # 4. تحليل التعلم العميق (Deep Learning) واستخراج الانتباه
        inputs = self.tokenizer(
            cleaned_text,
            max_length=256,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        ).to(self.device)

        with torch.no_grad():
            # تفعيل output_attentions=True لجلب أوزان التركيز
            outputs = self.model(**inputs, output_attentions=True)
            probs = F.softmax(outputs.logits, dim=1)

            # حساب حيرة الموديل (AI Hesitation)
            probs_1d = probs[0]
            sorted_probs, sorted_indices = torch.sort(probs_1d, descending=True)

            top1_prob = sorted_probs[0].item() * 100
            top2_prob = sorted_probs[1].item() * 100
            ai_diff = top1_prob - top2_prob 

            predicted_class = sorted_indices[0].item()
            confidence = probs[0][predicted_class].item() * 100
            
            # استخراج الأوزان وتحويلها لنسبة مئوية (Weights %)
            top_ai_weights = []
            if hasattr(outputs, 'attentions') and outputs.attentions is not None and len(outputs.attentions) > 0:
                last_layer_attn = outputs.attentions[-1]
                cls_attention = last_layer_attn[0, :, 0, :].mean(dim=0)
                tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
                
                valid_tokens = []
                total_weight = 0.0
                
                for t, w in zip(tokens, cls_attention):
                    clean_t = t.replace('##', '')
                    if t not in ['[CLS]', '[SEP]', '[PAD]'] and len(clean_t) > 1:
                        valid_tokens.append((clean_t, w.item()))
                        total_weight += w.item()
                
                # تحويل الوزن لنسبة مئوية من إجمالي الانتباه
                token_weights = []
                for t, w in valid_tokens:
                    percentage = (w / total_weight) * 100 if total_weight > 0 else 0
                    token_weights.append((t, round(percentage, 1)))
                    
                token_weights.sort(key=lambda x: x[1], reverse=True)
                
                # إرجاع أعلى 4 كلمات بدون تكرار
                seen = set()
                for t, w in token_weights:
                    if t not in seen:
                        top_ai_weights.append((t, w))
                        seen.add(t)
                    if len(top_ai_weights) == 4:
                        break

        dl_sentiment = self.labels_map[predicted_class]

        # 5. طبقة الذكاء الهجين (Hybrid Guardrails)
        final_sentiment = dl_sentiment
        lexicon_conflict = False
        
        # استخراج أعداد كلمات القاموس
        pos_words_count = len(rule_results["lexicon_details"]["pos_words"])
        neg_words_count = len(rule_results["lexicon_details"]["neg_words"])
        word_count = len(raw_text.split())

        # ---------------------------------------------------------
        # 🌟 1. تحجيم التضارب المعجمي (Lexicon Mixed Guardrail)
        # ---------------------------------------------------------
        # لا نعتبره تضارباً يغير النتيجة إذا كان الذكاء الاصطناعي واثقاً (>= 70%)
        # هذا يحمي المصطلحات المصرية (مثل: "عاش يا وحش") حيث يفهم الموديل السياق
        if confidence >= 50.0:
            lexicon_mixed = False
        else:
            lexicon_mixed = (pos_words_count > 0 and neg_words_count > 0)

        # ---------------------------------------------------------
        # 🌟 2. تحجيم حيرة الذكاء الاصطناعي (AI Hesitation Guardrail)
        # ---------------------------------------------------------
        ai_hesitation = False
        if word_count > 3: # تجاهل الجمل القصيرة جداً
            # تردد شديد (الموديل مشتت تماماً)
            if top1_prob < 55.0 and ai_diff < 5.0:
                ai_hesitation = True
            # أو تردد متوسط ولكن يصحبه تضارب حقيقي في القاموس
            elif top1_prob < 65.0 and lexicon_mixed:
                ai_hesitation = True

        # =========================================================
        # الأولويات الصارمة (Strict Guardrails)
        # =========================================================
        if rule_results.get("has_positive_negation"):
            final_sentiment = "إيجابي"
            lexicon_mixed = False 
            ai_hesitation = False
            
        elif rule_results["has_sarcasm"] and final_sentiment == "إيجابي":
            final_sentiment = "سلبي" 
            lexicon_mixed = False
            ai_hesitation = False
            
        elif rule_results["has_negation"] and final_sentiment == "إيجابي":
            final_sentiment = "سلبي"
            lexicon_mixed = False
            ai_hesitation = False

        # قاعدة تغليب المعجم الإيجابي الخالص على التعلم العميق المتردد
        if pos_words_count > 0 and neg_words_count == 0 and final_sentiment == "سلبي":
            if confidence < 65.0:
                final_sentiment = "إيجابي"
                lexicon_mixed = False
                ai_hesitation = False
                rule_results["triggered_tags"].append("تغليب المعجم الإيجابي على تردد الذكاء الاصطناعي")

        # =========================================================
        # تقييم المشاعر المختلطة (يطبق فقط إذا لم تتدخل القواعد الصارمة)
        # =========================================================
        if lexicon_mixed or ai_hesitation:
            final_sentiment = "مشاعر مختلطة"
            if lexicon_mixed:
                rule_results["triggered_tags"].append("تضارب معجمي (كلمات إيجابية وسلبية)")
            if ai_hesitation:
                rule_results["triggered_tags"].append(f"حيرة الذكاء الاصطناعي (الفرق {round(ai_diff,1)}% فقط)")
        
        # ==========================================
        # 💡 التحديث الذكي للقاموس الديناميكي (Self-Learning Guardrails)
        # ==========================================
        from database.cloud_memory import update_dynamic_lexicon

        if confidence >= 85.0 and final_sentiment in ["إيجابي", "سلبي"]:
            # 1. جلب أنواع الكلمات في الجملة باستخدام UDPipe
            pos_dict = self.udpipe.get_word_pos_dict(cleaned_text)
            
            # 2. قائمة حظر للكلمات المساعدة (Stop-words & Amplifiers)
            blacklist = ["كمان", "عشان", "جدا", "اوي", "خالص", "جداً", "اللي", "كده", "بقى", "طب", "ده", "دي", "انا", "انت"]
            
            for word, weight in top_ai_weights:
                if weight >= 10.0:
                    clean_w = word.replace('##', '') # تنظيف مقاطع BERT
                    
                    if len(clean_w) >= 2 and clean_w not in blacklist:
                        # البحث عن نوع الكلمة 
                        word_pos = "UNKNOWN"
                        for w, pos in pos_dict.items():
                            if clean_w in w:
                                word_pos = pos
                                break
                        
                        # 3. الفلترة النحوية: استبعاد الضمائر، حروف الجر، وأدوات الربط
                        if word_pos not in ["PRON", "ADP", "DET", "CCONJ", "SCONJ", "PART", "NUM", "PUNCT"]:
                            
                            # 4. الحيلة اللسانية للعامية المصرية (ECA Heuristic):
                            # الشيء المُقيّم (Aspect) غالباً يبدأ بـ "ال" (الاكل، المطعم، التليفون)
                            # المشاعر (Opinion) غالباً تأتي نكرة (يع، زبالة، تحفة، حلو، سيء)
                            is_aspect_noun = (word_pos == "NOUN" and clean_w.startswith("ال"))
                            
                            if not is_aspect_noun:
                                update_dynamic_lexicon(clean_w, final_sentiment)
                    
        # 6. بناء التقرير الشامل وإرجاعه للواجهة
        return {
            "original_text": raw_text,
            "final_sentiment": final_sentiment,
            "dl_confidence": round(confidence, 2),
            "dl_original_prediction": dl_sentiment,
            "top_ai_weights": top_ai_weights,
            "has_sarcasm": rule_results["has_sarcasm"],
            "has_negation": rule_results["has_negation"],
            "triggered_rules": rule_results["triggered_tags"],
            "matched_segments": rule_results["matched_segments"],
            "lexicon_conflict": lexicon_conflict,
            "lexicon_score": rule_results["lexicon_score"],
            "lexicon_pos_words": rule_results["lexicon_details"]["pos_words"],
            "lexicon_neg_words": rule_results["lexicon_details"]["neg_words"]
        }