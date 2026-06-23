# database/cloud_memory.py
import os
import hashlib
import datetime
import firebase_admin
from firebase_admin import credentials, db

# رابط قاعدة البيانات الخاصة بك
DATABASE_URL = '' 

#  دمج مفاتيح السحابة مباشرة كـ Dictionary لحمايتها عند تحويل البرنامج لـ exe
FIREBASE_DICT = {
  
}

def init_firebase():
    """تهيئة الاتصال بـ Firebase باستخدام القاموس مباشرة"""
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(FIREBASE_DICT)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
            return True
        except Exception as e:
            print(f"❌ Error initializing Firebase: {e}")
            return False
    return True

# ==========================================
# 1. نظام تصحيح النتائج (User Feedback)
# ==========================================
def save_user_feedback(text, ai_original_prediction, corrected_sentiment, is_sarcastic):
    """رفع تصحيح المستخدم إلى قاعدة البيانات مع حفظ تنبؤ الذكاء الاصطناعي الأصلي"""
    if not init_firebase(): return False
    try:
        ref = db.reference('user_feedback')
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        ref.child(text_hash).set({
            'original_text': text,
            'ai_original_prediction': ai_original_prediction,  # النتيجة الأصلية للموديل قبل التصحيح
            'corrected_sentiment': corrected_sentiment,        # النتيجة الصحيحة من المستخدم
            'is_sarcastic': is_sarcastic,
            'timestamp': {".sv": "timestamp"}
        })
        return True
    except Exception as e:
        print(f"❌ Error saving feedback: {e}")
        return False

def get_all_feedback():
    """جلب كل التقييمات المحفوظة مسبقاً لبناء الذاكرة المؤقتة (Cache)"""
    if not init_firebase(): return {}
    try:
        ref = db.reference('user_feedback')
        data = ref.get()
        if data:
            return {
                val['original_text']: {
                    'sentiment': val['corrected_sentiment'],
                    'ai_original_prediction': val.get('ai_original_prediction', 'غير معروف'), 
                    'sarcasm': val.get('is_sarcastic', False)
                } 
                for key, val in data.items() if 'original_text' in val
            }
        return {}
    except Exception as e:
        print(f"❌ Error getting feedback: {e}")
        return {}
# ==========================================
# 2. نظام إدارة بيانات المستخدمين (User Profiles)
# ==========================================
def sync_user_profile_to_cloud(data):
    """رفع بيانات المستخدم الكاملة للسحابة بما فيها العداد"""
    if not init_firebase(): return
    try:
        device_id = data.get("device_id")
        if not device_id: return
        
        ref = db.reference(f'users/{device_id}')
        # تحديث الوقت الأخير للنشاط قبل الرفع
        data["last_active"] = str(datetime.datetime.now())
        
        ref.set(data)
        print(f"☁️ [سحابة] تم مزامنة بيانات الملف الشخصي والعداد بنجاح.")
    except Exception as e:
        print(f"⚠️ [خطأ] فشل رفع بيانات المستخدم للسحابة: {e}")
        
def get_app_update_info():
    """جلب بيانات آخر تحديث متاح للموديل من السحابة"""
    if not init_firebase(): return None
    try:
        ref = db.reference('app_updates')
        return ref.get()
    except Exception as e:
        print(f"❌ Error checking updates: {e}")
        return None
# ==========================================
# 3. نظام القاموس الديناميكي ذاتي التعلم (Dynamic Lexicon)
# ==========================================
import re

def update_dynamic_lexicon(word, sentiment):
    """
    إضافة الكلمة إلى القاموس السحابي الديناميكي مع تحديث عداد المشاعر.
    Firebase Keys لا تقبل الرموز . # $ [ ] لذا نقوم بتنظيف الكلمة أولاً.
    """
    if not init_firebase() or not word or not isinstance(word, str): 
        return False
        
    try:
        # تنظيف الكلمة من أي رموز غير مسموحة في قواعد بيانات Firebase
        clean_word = re.sub(r'[.#$\[\]]', '', word).strip()
        
        # تجاهل الحروف المفردة والمسافات
        if len(clean_word) < 2: 
            return False 
            
        ref = db.reference(f'dynamic_lexicon/{clean_word}')
        
        # جلب البيانات القديمة لو موجودة، أو إنشاء سجل جديد
        current_data = ref.get() or {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        
        # تحديد المفتاح بناءً على تصنيف المشاعر
        sentiment_key = "neutral"
        if sentiment == "إيجابي": sentiment_key = "positive"
        elif sentiment == "سلبي": sentiment_key = "negative"
        elif sentiment == "مشاعر مختلطة": sentiment_key = "mixed"
        
        # زيادة العداد بمقدار 1
        current_data[sentiment_key] = current_data.get(sentiment_key, 0) + 1
        
        # رفع التحديث للسحابة
        ref.set(current_data)
        # print(f"🧠 [قاموس ديناميكي] تم تعلم كلمة جديدة: '{clean_word}' كـ {sentiment}")
        return True
    except Exception as e:
        print(f"❌ [خطأ] فشل تحديث القاموس الديناميكي: {e}")
        return False

def get_dynamic_lexicon():
    """جلب القاموس الديناميكي بالكامل من السحابة لدمجه مع القاموس الأساسي"""
    if not init_firebase(): 
        return {}
    try:
        ref = db.reference('dynamic_lexicon')
        data = ref.get()
        return data if data else {}
    except Exception as e:
        print(f"❌ [خطأ] فشل جلب القاموس الديناميكي: {e}")
        return {}
