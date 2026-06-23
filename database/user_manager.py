# database/user_manager.py
import json
import os
import string
import random
import hashlib
from database.cloud_memory import sync_user_profile_to_cloud, init_firebase, db

LOCAL_USER_FILE = 'user_data.json'
APP_VERSION = "V1.0"

class UserManager:
    def __init__(self):
        self.current_user = self.load_local_user()

    def generate_serial(self):
        """توليد رقم تسلسلي عشوائي من 18 حرف ورقم"""
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(18))

    def hash_password(self, password):
        """تشفير كلمة المرور للحماية الأساسية"""
        return hashlib.sha256(password.encode()).hexdigest()

    def load_local_user(self):
        """التحقق من وجود بيانات المستخدم محلياً"""
        if os.path.exists(LOCAL_USER_FILE):
            try:
                with open(LOCAL_USER_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: 
                return None
        return None

    def save_local_user(self, data):
        """حفظ بيانات المستخدم في ملف JSON محلي"""
        with open(LOCAL_USER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        self.current_user = data

    def register(self, name, email, password, profession):
        """تسجيل مستخدم جديد (بالمهنة) ورفعه للسحابة"""
        init_firebase()
        try:
            users_ref = db.reference('users')
            all_users = users_ref.get()
            
            # التحقق إذا كان الإيميل مسجل مسبقاً
            if all_users:
                for uid, udata in all_users.items():
                    if udata.get('email') == email:
                        return False, "البريد الإلكتروني مسجل مسبقاً!"
            
            serial_id = self.generate_serial()
            user_data = {
                "device_id": serial_id,
                "name": name,
                "email": email,
                "password": self.hash_password(password),
                "profession": profession, #  حفظ المهنة
                "app_version": APP_VERSION,
                "ops_count": 0,
                "last_active": ""
            }
            
            # الرفع للسحابة والحفظ المحلي
            sync_user_profile_to_cloud(user_data)
            self.save_local_user(user_data)
            return True, "تم التسجيل بنجاح!"
            
        except Exception as e:
            return False, f"خطأ في الاتصال بالسحابة: {str(e)}"

    def login(self, email, password):
        """تسجيل الدخول والتحقق من السحابة"""
        init_firebase()
        try:
            users_ref = db.reference('users')
            all_users = users_ref.get()
            hashed_pw = self.hash_password(password)
            
            if all_users:
                for uid, udata in all_users.items():
                    if udata.get('email') == email and udata.get('password') == hashed_pw:
                        self.save_local_user(udata)
                        return True, "تم تسجيل الدخول بنجاح!"
            return False, "البريد الإلكتروني أو كلمة المرور غير صحيحة."
        except Exception as e:
            return False, f"خطأ في الاتصال بالسحابة: {str(e)}"

    def update_ops_count(self, new_count):
        """تحديث عدد العمليات محلياً وسحابياً"""
        if self.current_user:
            self.current_user['ops_count'] = new_count
            self.save_local_user(self.current_user)
            sync_user_profile_to_cloud(self.current_user)
