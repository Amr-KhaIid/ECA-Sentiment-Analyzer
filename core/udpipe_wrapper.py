# core/udpipe_wrapper.py
import ufal.udpipe as udpipe
import os

class UDPipeWrapper:
    def __init__(self, model_path="models/arabic-padt-ud-2.5-191206.udpipe"):
        """تحميل موديل UDPipe لاستخراج أصل الكلمات (Lemmatization) وأقسام الكلام"""
        abs_path = os.path.abspath(model_path)
        
        if not os.path.exists(abs_path):
            print(f"⚠️ تنبيه: موديل UDPipe غير موجود في {abs_path}. سيتم العمل بدون الـ Lemmatization مؤقتاً.")
            self.model = None
            return
            
        print("⏳ جاري تحميل موديل UDPipe اللغوي...")
        self.model = udpipe.Model.load(abs_path)
        
        if not self.model:
            print("❌ فشل تحميل موديل UDPipe!")
            return
            
        self.pipeline = udpipe.Pipeline(
            self.model,
            "tokenize",
            udpipe.Pipeline.DEFAULT,
            udpipe.Pipeline.DEFAULT,
            "conllu"
        )
        print("✅ تم تحميل موديل UDPipe بنجاح!")

    def get_lemmas(self, text):
        """
        ياخد الجملة ويرجع جملة موازية متكونة من الـ Lemmas (الأصول) فقط
        مثال: "المنتجات سيئة" -> "منتج سيء"
        """
        if not self.model or not text.strip():
            return text # إرجاع النص الأصلي كـ Fallback لو الموديل مش موجود
            
        processed = self.pipeline.process(text)
        lemmas = []
        
        for line in processed.split("\n"):
            if line.startswith("#") or line.strip() == "": 
                continue
                
            parts = line.split("\t")
            if len(parts) >= 3:
                word = parts[1]
                lemma = parts[2]
                
                # لو الموديل معرفش يجيب الأصل ورجع "_" نستخدم الكلمة الأصلية
                if lemma == '_':
                    lemmas.append(word)
                else:
                    lemmas.append(lemma)
                    
        return " ".join(lemmas)

    def get_word_pos_dict(self, text):
        """
        تحليل الجملة واستخراج نوع كل كلمة (اسم، فعل، صفة، حرف، إلخ)
        هذه الدالة تستخدم لمنع تسجيل الكلمات غير المعبرة عن مشاعر في القاموس الديناميكي
        """
        if not self.model or not text.strip():
            return {}
            
        processed = self.pipeline.process(text)
        pos_dict = {}
        
        for line in processed.split("\n"):
            if line.startswith("#") or line.strip() == "": 
                continue
                
            parts = line.split("\t")
            if len(parts) >= 4:
                word = parts[1]
                pos = parts[3] # (UPOS) Universal Part of Speech
                pos_dict[word] = pos
                
        return pos_dict