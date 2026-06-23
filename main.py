# main.py
import sys
from PyQt6.QtWidgets import QApplication
from ui.splash_login import SplashScreen, AuthWindow
from ui.main_window import MainWindow
from database.user_manager import UserManager

class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.user_manager = UserManager()
        
        # 1. تهيئة شاشة التحميل (Splash Screen)
        self.splash = SplashScreen()
        self.splash.finished.connect(self.check_auth)
        self.splash.show()
        self.splash.start()

    def check_auth(self):
        """التحقق بعد انتهاء التحميل: هل يوجد مستخدم محلي؟"""
        if self.user_manager.current_user is not None:
            # المستخدم موجود -> افتح الواجهة الرئيسية مباشرة
            self.show_main_window()
        else:
            # المستخدم غير موجود -> افتح شاشة تسجيل الدخول
            self.auth_window = AuthWindow()
            self.auth_window.auth_successful.connect(self.show_main_window)
            self.auth_window.show()

    def show_main_window(self):
        """عرض الواجهة الرئيسية وتمرير بيانات المستخدم لها"""
        # إعادة قراءة بيانات المستخدم للتأكد (في حال أنه للتو قام بالتسجيل)
        self.user_manager = UserManager() 
        user_data = self.user_manager.current_user
        
        self.main_window = MainWindow()
        
        # تمرير الاسم وعداد العمليات من الـ JSON للواجهة الرئيسية
        if user_data:
            self.main_window.current_user_name = user_data.get("name", "مستخدم")
            self.main_window.total_ops_count = user_data.get("ops_count", 0)
            self.main_window.update_greeting()
            self.main_window.ops_count_label.setText(str(self.main_window.total_ops_count))
            
            # ربط دالة تحديث العمليات في الواجهة ليتم حفظها سحابياً أيضاً
            original_increment = self.main_window.increment_ops
            def new_increment(count=1):
                original_increment(count)
                self.user_manager.update_ops_count(self.main_window.total_ops_count)
            self.main_window.increment_ops = new_increment

        self.main_window.show()

if __name__ == "__main__":
    controller = AppController()
    sys.exit(controller.app.exec())