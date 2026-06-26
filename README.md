# ECA Sentiment Analyzer 🎭

محلل المشاعر ECA (Emotion & Classification Analyzer) - أداة متقدمة لتحليل المشاعر في النصوص.

## البنية الهرمية للمشروع 📁

```
ECA_Analyzer_Project/
│
├── main.py                    # نقطة البداية للبرنامج
├── requirements.txt           # المكتبات المطلوبة
├── firebase_credentials.json  # بيانات Firebase
│
├── 📁 core/                   # المكونات الأساسية
│   ├── hybrid_analyzer.py     # محلل هجين
│   ├── rules_extractor.py     # استخراج القواعد
│   ├── text_cleaner.py        # تنظيف النصوص
│   └── udpipe_wrapper.py      # غلاف UDPipe
│
├── 📁 data_processing/        # معالجة البيانات
│   └── csv_handler.py         # معالجة ملفات CSV
│
├── 📁 database/               # قاعدة البيانات
│   ├── cloud_memory.py        # Firebase Cloud
│   └── user_manager.py        # إدارة المستخدمين
│
├── 📁 models/                 # نماذج التعلم الآلي
│   └── Active model/
│
└── 📁 ui/                     # الواجهة الرسومية
    ├── main_window.py
    └── 📁 assets/            # الموارد والصور
```

## المميزات ✨

- تحليل هجين للمشاعر (Rules-Based + ML)
- دعم النصوص العربية
- واجهة رسومية سهلة الاستخدام
- تكامل مع Firebase للتخزين السحابي

## المتطلبات 📦

انظر إلى `requirements.txt` للحصول على قائمة كاملة بالمكتبات المطلوبة.

## التثبيت والتشغيل 🚀

```bash
# تثبيت المكتبات
pip install -r requirements.txt

# تشغيل البرنامج
setup Download URL: 
```

---
**تطوير بواسطة:** Amr-KhaIid
