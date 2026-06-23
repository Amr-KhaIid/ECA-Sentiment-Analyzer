# core/rules_extractor.py
import pandas as pd
import os
import re

class RuleFeatureExtractor:
    def __init__(self):
        # الكلمات المساعدة للنفي
        self.helpers = r"(?:كان|كانت|طلع|طلعت|يطلع|بيطلع|بقا|بقى|يبقى|شكله|شكلها|طعمه|طعمها|لونه|لونها|حاسس|حاسه|ريحتها|ريحته|ملمسه|ملمسها)"

        # 🌟 قاعدة النفي الإيجابي (مُضيَّقة للعبارات الدينية الخالصة فقط)
        self.positive_negation_patterns = [
            r"\bما شاء الله تبارك الله\b",
            r"\bتبارك الله\b",
            r"\bلا إله إلا الله\b",
            r"\bسبحان الله\b",
            r"\bالحمد ?لله\b",
            r"\bما شاء الله عليك\b",
            r"\bما شاء الله\b",
            r"\bإن شاء الله\b"
        ]
        self.positive_negation = r"(?:" + "|".join(self.positive_negation_patterns) + r")"

        # 🌟 قواعد النفي (مُحسَّنة)
        self.negation_rules = {
            "MSA_Particles": rf"\b(?:غير|لا|ليس|دون|بلا|بدون|من غير)\s+(?:{self.helpers}\s+)?((?:\w+\s*){{1,3}})",
            "Prohibition_Nahy": rf"\b(?:بلاش|اوعي|اوعى|اياك|إياك)\s+(?:{self.helpers}\s+)?((?:\w+\s*){{1,3}})",
            "Lexical_Intrinsic": rf"\b(?:يفتقر ل|يفتقر الى|خالي من|انعدام|نقص)\s+((?:\w+\s*){{1,3}})",
            "Prefix_La": r"\bاللا([ا-ي]+)\b",
            "Exception_Flaw": rf"\b(?:الا|إلا|غير)\s+((?:\w+\s*){{1,3}})",
            "Negated_Helper": rf"(?:و|ف)?ما\s*(?:كان|طلع|بقا|بقى|عاد|حس|لقي|يطلع|يكون|تبق)[ا-ي]*ش\s+((?:\w+\s*){{1,3}})",
            "Direct_Mish": rf"(?:و|ف|ب|ك)?مش\s+(?:{self.helpers}\s+)?((?:\w+\s*){{1,3}})",
            "Distanced_Mish": rf"(?:و|ف|ب|ك)?مش\s+(?:خالص|جدا|قوي|اوي|اصلا|ولا)\s+(?:{self.helpers}\s+)?((?:\w+\s*){{1,3}})",
            "Circumfix_Ma_Sh": r"(?:و|ف)?ما\s*([ا-ي]+)ش",
            "Absolute_Distance": r"(?:و|ف|ب|ك)?(?:مفيش|مفيهاش|مفيهوش|ولا)\s+(?:[ا-ي]+\s+){0,3}((?:\w+\s*){1,3})",
            "Negation_Wala": rf"\bولا\s*((?:\w+\s*){{1,3}})"
        }

        # 🌟 التناقضات الرقمية
        self.numerical_contradictions = {
            "Performance_Contradiction": {
                "pos": r"(?:اسرع|صاروخ|سريع|طلقه|طياره|ثانيه)",
                "neg": r"(?:نص ساعه|ساعه|ساعات|سنين|قرن|ايام|يومين|اسبوع)"
            },
            "Battery_Contradiction": {
                "pos": r"(?:بطاريه|شحن|بيقعد|ممتازه|طول اليوم|ما شاء الله)",
                "neg": r"(?:دقيقه|دقيقتين|دقايق|ثواني)"
            }
        }

        # 🌟 أنماط السخرية (الأصلية + السياقات الخدمية)
        self.sarcasm_patterns = {
            "Religious_Praise_Mockery": r"\b(?:بسم الله ما شاء الله|يا صلاه النبي|اللهم صلي على النبي|تبارك الله)\b.*?\b(?:غباء|هبل|عبط|فشل|بوظ|خرب|هنج|فصل|بطيء|زباله|ضياع)\b",
            "Intellectual_Mockery": r"\b(?:عبقري|فنان|ذكي|فلته|عالمي|مبدع|تكنولوجيا فضائيه)\b.*?\b(?:غلط|فشل|هنج|بطيء|تايه|بلح|فنكوش)\b",
            "Thermal_Mockery": r"\b(?:زي|اكني|كاني|كأني|تحس|شبه)\b.*?\b(?:دفايه|مكوه|فرن|بوتجاز|بيض|شاي|نار|ولعه|صهد)\b",
            "Speed_Mockery": r"\b(?:زي|اكني|كاني|كأني|تحس|شبه)\b.*?\b(?:سلحفاه|حلزونه|نمله|مشلول|ميت|ميتين|جماد)\b",
            "Material_Mockery": r"\b(?:زي|اكني|كاني|كأني|تحس|شبه)\b.*?\b(?:حديده|خشب|بلاستيك|لعبه|صفيح|كرتون|طوبه|كردة|خردة)\b",
            "Skeptical_Question": r"\b(?:هو ده|بذمتك ده|مين يصدق|عجبك كده|يا فرحتي ب|مبروك علينا ال|فين ال|حد يشتري|مين يجيب)\b.*?\b(?:تحديث|تطوير|سرعه|كاميرا|اداء|توفير|عظمه)\b",
            "False_Gratitude": r"\b(?:تسلم ايدكم|عاش جدا|شكرا بجد|كتر خيركم|برافو عليكم|منور يا)\b.*?\b(?:بوظتوا|خربتوا|ضيعتوا|فشلتوا|قرفتونا)\b",
            "Temporal_Lag": r"\b(?:ردوا|حلوا|شحن|فتح|جاب|وصل|استنيت|مستني)\b.*?\b(?:سنه|سنين|قرن|دهر|جيل|عمر|موسم|عصور|ماتوا|محلجوش)\b",
            "Expectation_Crash": r"\b(?:زي ما بيقولوا|زي الاعلانات|كلام ورق|كلام جرايد|زي الصور)\b.*?\b(?:مختلف|وحش|سيء|مقلب|فنكوش)\b",
            "Service_Thanks_Sarcasm": r"\b(?:شكر[اًا]?\s*(?:على|ل)\s*الاهتمام)\b.*\b(?:سيء|زفت|فاشل|تعب|وجع)\b",
            "Service_Fake_Praise": r"\b(?:فاشل|زبالة|تعبان)\b.*\b(?:أحلى|أروع|أفضل)\s*(?:حاجة|شيء|تطبيق)\b",
            "Service_Praise_But": r"\b(?:حلو|جميل|را?ئع)\b.*\b(?:بس|لكن)\b.*\b(?:مش|لا|سيء|غبي)\b",
            "Service_Waste_Advice": r"\b(?:وفر|ريح)\s*(?:فلوسك|نفسك|وقتك)\b",
            "Service_Speed_Sarcasm": r"\b(?:سرعة|طيار|صاروخ)\b.*\b(?:مش|لا|بطيء|ماشي)\b"
        }

        # 🌟 تحميل قاموس NileULex
        self.lexicon_pos = set()
        self.lexicon_neg = set()
        self.load_nile_lexicon()

    def load_nile_lexicon(self):
        try:
            lexicon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NileULex_v0.27.csv')
            if os.path.exists(lexicon_path):
                df = pd.read_csv(lexicon_path, skiprows=9, header=0)
                for idx, row in df.iterrows():
                    term = str(row['Term']).strip()
                    polarity = str(row['Polarity']).strip()
                    if 'positive' in polarity:
                        self.lexicon_pos.add(term)
                    elif 'neg' in polarity:
                        self.lexicon_neg.add(term)
        except Exception as e:
            print(f"⚠️ لم يتم تحميل قاموس NileULex: {e}")

    # 👈 التعديل هنا: الدالة بقت تستقبل lemmatized_text
    def analyze_rules(self, text, lemmatized_text=""):
        results = {
            "has_negation": False,
            "has_sarcasm": False,
            "has_positive_negation": False,
            "triggered_tags": [],
            "matched_segments": [],
            "lexicon_score": 0,
            "lexicon_details": {"pos_words": [], "neg_words": []}
        }

        # 1. فحص النفي الإيجابي (ديني) مع حماية من النفي الصريح
        match = re.search(self.positive_negation, text)
        if match:
            if not re.search(r"(?:مش|مفيش|مافيش|ما\w+ش)", text):
                results["has_positive_negation"] = True
                results["triggered_tags"].append("Positive Negation: Flawless")
                results["matched_segments"].append(match.group(0))

        # 2. فحص النفي العادي
        if not results["has_positive_negation"]:
            for name, pattern in self.negation_rules.items():
                match = re.search(pattern, text)
                if match:
                    results["has_negation"] = True
                    results["triggered_tags"].append(f"Negation: {name}")
                    results["matched_segments"].append(match.group(0))

        # 3. التناقض الرقمي
        for name, patterns in self.numerical_contradictions.items():
            pos_match = re.search(patterns["pos"], text)
            neg_match = re.search(patterns["neg"], text)
            if pos_match and neg_match:
                results["has_sarcasm"] = True
                results["triggered_tags"].append(f"Contradiction: {name}")
                results["matched_segments"].append(f"{pos_match.group(0)} ... {neg_match.group(0)}")

        # 4. فحص السخرية
        for name, pattern in self.sarcasm_patterns.items():
            match = re.search(pattern, text)
            if match:
                results["has_sarcasm"] = True
                results["triggered_tags"].append(f"Sarcasm: {name}")
                results["matched_segments"].append(match.group(0))

        # 5. فحص القاموس (باستخدام أصل الكلمة Lemma لزيادة الدقة)
        clean_words = re.sub(r'[^\w\s]', ' ', text).split()
        lemma_words = lemmatized_text.split() if lemmatized_text else []
        
        pos_count = 0
        neg_count = 0

        backup_pos = {"تحفة", "عظمة", "شيك", "سريع", "حلوة", "حلو", "ممتاز", "عظيم", "روعة", "عاش", "لقطة"}
        backup_neg = {"زبالة", "تقيل", "بيهنج", "وحش", "سيء", "بطيء", "يفصل", "قرف", "يع", "زفت"}

        for i, word in enumerate(clean_words):
            core_word = re.sub(r'^(و|ف|ب)', '', word) if len(word) > 3 else word
            
            # 👈 سحب أصل الكلمة من UDPipe لتوسيع نطاق البحث في القاموس
            lemma = lemma_words[i] if i < len(lemma_words) else core_word

            # فحص الكلمة الأصلية أو الجذر (Lemma)
            if word in self.lexicon_pos or core_word in self.lexicon_pos or lemma in self.lexicon_pos or core_word in backup_pos or lemma in backup_pos:
                pos_count += 1
                results["lexicon_details"]["pos_words"].append(core_word)
                
            if word in self.lexicon_neg or core_word in self.lexicon_neg or lemma in self.lexicon_neg or core_word in backup_neg or lemma in backup_neg:
                neg_count += 1
                results["lexicon_details"]["neg_words"].append(core_word)

        results["lexicon_score"] = pos_count - neg_count
        return results