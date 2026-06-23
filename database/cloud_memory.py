# database/cloud_memory.py
import os
import hashlib
import datetime
import firebase_admin
from firebase_admin import credentials, db

# رابط قاعدة البيانات الخاصة بك
DATABASE_URL = 'https://hybrid-ai-memory-default-rtdb.firebaseio.com/' 

#  دمج مفاتيح السحابة مباشرة كـ Dictionary لحمايتها عند تحويل البرنامج لـ exe
FIREBASE_DICT = {
  "type": "service_account",
  "project_id": "hybrid-ai-memory",
  "private_key_id": "a8818634636f28c8d380a007cf6c9458d0028eb3",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDA64+zvJpn2PLF\nD30VAmC9ThwA256Ho5vNk/xPzd8XSD3YtPxd0lHiw5YoTK1V9FkZTQJpysb0EZ7c\nnS/AaztWprwEFM3VbbUImf9joDNIc7qFXelQU1i+ija0AlC6tt/qC7OTtNr+OQMn\naLzHawWxEc1GoAcW2FwcCUKEa0fxkijrdbvgtnhI+HSq9EUnxtcl9ECh7fUDsOiS\nHHygz6lDsvGt+5ZCkt7Mngi1kxU762ci6oq1b4P6aqgHd4FR/M0YxGv8OGf5QEcu\nOBAHNQ2uiKa9vpFP7khg/O3JysH8reCm80+kev0fU+t9dAtq/yMrsgFW9iiBgFfR\n2QUunjktAgMBAAECggEAHiq3pdtwKZz7GWV6obZlejSknF27RGqJCnSBl9kRcYqS\nYTir3d/tfhAngtW6pR44cIRiRDi5M6EtvkG2Hdimxr372IeISD+Hd3jdPq7mVgYC\nvKgau7zMu77RHwTdqtS93tNFmWtGc0pm+9qc6nIJyc6G0uxjL2dVv+ySwjIkZdm3\nIu03n2wU1dHqWWILZmxAArWok36zRnPocvnmypr2YhgTYcUC2TMfXreFQa2uHqmD\nMPXHt2uHLKUZMx4Vmtwd8IPofYbOwdVVe8K9bKHqMoTWDUAfp3ngAKT54uZT+pOx\nxFBuzvNGdwrq5aOYXm1FwNSjZ+8YaPB+18vQLLQ1AQKBgQD5sVifSumbqT4UzkhH\n8Z1fu/mx4ouos5jC8q6nWbvzoTDk0gqjMt78r3Vn5u6RWjx9zIhh3DgEnSk3cc4V\nmsvNuKPNJhV+8fsaBnKjdp7St0Xn9TNCunwxuNkjMMuwHYCOsQwLf9Qz0AaYlzCw\n5f7WkO6KDxr9JxqAqL92AidcJQKBgQDFyxdzzRCApfRTMH8axtuRBR2l5pJKldw4\nosSFbWc4NNUMadIO4mOII2GvKn9ZZ/zN5aWwnMhrYCWD9s3GOKWvuM/bwMVGvTnN\nZx25uF9NcMo5op6RvcairzW20PKB9irQQvz4nhrCqDKyNgnZK4ewX7/2d45rs7SV\nmr6hi+FWaQKBgQCt6a9va88gg5XhCfjgW1Kgzp3RH5jkzQrWpg+uMlsuCxSyG/Ya\ny6Dy4Qbmcrux8+b0PBS2DJvb4tdFbff7plDTngpBJoiMXeDmtJz+a+2dmNeRA4FL\ntfYw764Vy7Pjm/jh6kEYdVWJLRibCZt5awi/zDzJXlIPB0B3YpHQkRl3HQKBgQDA\nfA5MsYmXyOjmdFGdm1xd2t6pbqN7Vi/EJhKdzoQe3LtgozK7LXGzMMuFjhP0zA/n\nx87g+xLH+/9GV06V0tbbFT2jHAxf9RJlZC43aMfGMzd5s1ohds/xzhS13s3Bz/CG\nUEqjICnmuYzshU48O/KGoAfOMTc2dOIOnVNbHyeh0QKBgQCsrA3t/oHKNRl7PPY4\neALVrqkRzvpVR7WD8NoV0URt7Njc4y43n5q2oKiNOLjPZlpWGacU9HpYy2druqR9\ndtX4lk91ELp9glwCZpqFfVj1ftNNGIrwxB0qoFYrS7vzJfWYVA43WTB4tSgaDe+4\nd8fzCRRlJJA9+XCPPTr1MBaM8g==\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-fbsvc@hybrid-ai-memory.iam.gserviceaccount.com",
  "client_id": "103232188913242734895",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40hybrid-ai-memory.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
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