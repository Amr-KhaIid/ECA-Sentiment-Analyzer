# ui/splash_login.py
import os
import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QProgressBar, QStackedWidget, QMessageBox, QFrame, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from database.user_manager import UserManager

class SplashScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(500, 300)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.frame = QFrame(self)
        self.frame.setFixedSize(500, 300)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 2px solid #89b4fa;
                border-radius: 15px;
            }
            QLabel { color: #cdd6f4; border: none; }
        """)

        layout = QVBoxLayout(self.frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("ECA Sentiment Analyzer")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #cba6f7;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("جاري تحميل النظام والتحقق من الملفات...")
        subtitle.setStyleSheet("font-size: 14px; margin-top: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar { border: 2px solid #45475a; border-radius: 5px; text-align: center; color: white; font-weight: bold; background-color: #313244;}
            QProgressBar::chunk { background-color: #a6e3a1; border-radius: 3px; }
        """)
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(20)

        self.status_label = QLabel("البدء...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; color: #f9e2af;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.counter = 0

        self.files_to_check = [
            ("main.py", 15),
            ("core/hybrid_analyzer.py", 35),
            ("core/rules_extractor.py", 55),
            ("models/Amr_MARBERTv2...", 90),
            ("بدء النظام...", 100)
        ]
        self.check_index = 0

    def start(self):
        self.timer.start(50)

    def update_progress(self):
        if self.check_index < len(self.files_to_check):
            file_name, target_prog = self.files_to_check[self.check_index]
            
            if self.counter < target_prog:
                self.counter += 1
                self.progress.setValue(self.counter)
                self.status_label.setText(f"التحقق من: {file_name}")
            else:
                self.check_index += 1
        else:
            self.timer.stop()
            time.sleep(0.5)
            self.finished.emit()
            self.close()

class AuthWindow(QWidget):
    auth_successful = pyqtSignal()

    def __init__(self):
        super().__init__()
        #  1. إخفاء حواف الويندوز وجعل الخلفية شفافة
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 620)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setObjectName("mainAuthWidget")
        self.user_manager = UserManager()
        self.drag_pos = QPoint()
        
        # 🌟 2. ستايل الواجهة مع تحديد الـ Border Radius المظبوط للبطاقة
        self.setStyleSheet("""
            QWidget#mainAuthWidget { background: transparent; font-family: Arial; }
            QFrame#card { 
                background-color: #181825; 
                border: 2px solid #45475a; 
                border-radius: 20px; 
            }
            QLabel { color: #cdd6f4; font-size: 14px; font-weight: bold; border: none; }
            
            QLineEdit, QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; padding: 10px; font-size: 14px; }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #89b4fa; }
            QComboBox::drop-down { border: none; }
            
            QCheckBox { color: #bac2de; font-size: 13px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #45475a; background-color: #313244; }
            QCheckBox::indicator:checked { background-color: #89b4fa; border: 1px solid #89b4fa; }
            
            QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 8px; font-size: 16px; font-weight: bold; padding: 10px; }
            QPushButton:hover { background-color: #b4befe; }
            
            QPushButton#linkBtn { background-color: transparent; color: #cba6f7; font-size: 14px; font-weight: normal; border: none; }
            QPushButton#linkBtn:hover { text-decoration: underline; color: #f5c2e7; }
            
            QPushButton#closeBtn { background: transparent; color: #f38ba8; font-size: 20px; font-weight: bold; padding: 0px; border: none; }
            QPushButton#closeBtn:hover { color: #e06c75; }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # البطاقة الرئيسية (الـ Box اللي هيظهر)
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setFixedSize(420, 600)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(30, 20, 30, 30)

        #  3. زرار الإغلاق المصمم خصيصاً للنافذة الشفافة
        top_bar = QHBoxLayout()
        self.close_btn = QPushButton("✖")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close)
        top_bar.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        self.card_layout.addLayout(top_bar)

        self.stacked_widget = QStackedWidget()
        self.setup_login_page()
        self.setup_signup_page()
        
        self.card_layout.addWidget(self.stacked_widget)
        self.layout.addWidget(self.card)

    #  4. تفعيل خاصية السحب (Drag) بالماوس لتحريك الشاشة
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()

    def setup_login_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0,0,0,0)
        
        title = QLabel("تسجيل الدخول")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #cba6f7; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_email = QLabel("البريد الإلكتروني")
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("أدخل بريدك الإلكتروني")

        lbl_pass = QLabel("كلمة المرور")
        self.login_pass = QLineEdit()
        self.login_pass.setPlaceholderText("أدخل كلمة المرور")
        self.login_pass.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_login = QPushButton("دخول 🚀")
        self.btn_login.clicked.connect(self.handle_login)

        btn_go_signup = QPushButton("ليس لديك حساب؟ إنشاء حساب جديد")
        btn_go_signup.setObjectName("linkBtn")
        btn_go_signup.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(lbl_email)
        layout.addWidget(self.login_email)
        layout.addSpacing(10)
        layout.addWidget(lbl_pass)
        layout.addWidget(self.login_pass)
        layout.addSpacing(30)
        layout.addWidget(self.btn_login)
        layout.addSpacing(10)
        layout.addWidget(btn_go_signup)
        layout.addStretch()

        self.stacked_widget.addWidget(page)

    def setup_signup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0,0,0,0)
        
        title = QLabel("إنشاء حساب جديد")
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #cba6f7; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.signup_name = QLineEdit()
        self.signup_name.setPlaceholderText("الاسم بالكامل")

        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("البريد الإلكتروني")

        self.signup_pass = QLineEdit()
        self.signup_pass.setPlaceholderText("كلمة المرور")
        self.signup_pass.setEchoMode(QLineEdit.EchoMode.Password)

        self.signup_profession = QComboBox()
        self.signup_profession.addItems(["اختر المهنة...", "طالب", "موظف", "باحث", "مؤسسة / شركة", "أخرى"])
        
        self.terms_checkbox = QCheckBox("أوافق على سياسة الخصوصية وحقوق الملكية للمشروع")

        self.btn_signup = QPushButton("إنشاء الحساب 🌟")
        self.btn_signup.clicked.connect(self.handle_signup)

        btn_go_login = QPushButton("لديك حساب بالفعل؟ تسجيل الدخول")
        btn_go_login.setObjectName("linkBtn")
        btn_go_login.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        layout.addWidget(title)
        layout.addWidget(QLabel("الاسم:"))
        layout.addWidget(self.signup_name)
        layout.addWidget(QLabel("البريد الإلكتروني:"))
        layout.addWidget(self.signup_email)
        layout.addWidget(QLabel("كلمة المرور:"))
        layout.addWidget(self.signup_pass)
        layout.addWidget(QLabel("المهنة / التخصص:"))
        layout.addWidget(self.signup_profession)
        layout.addSpacing(10)
        layout.addWidget(self.terms_checkbox)
        layout.addSpacing(15)
        layout.addWidget(self.btn_signup)
        layout.addWidget(btn_go_login)
        layout.addStretch()

        self.stacked_widget.addWidget(page)

    def handle_login(self):
        email = self.login_email.text().strip()
        password = self.login_pass.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال البريد الإلكتروني وكلمة المرور.")
            return

        self.btn_login.setText("جاري التحقق...")
        self.btn_login.setEnabled(False)
        
        success, msg = self.user_manager.login(email, password)
        if success:
            self.auth_successful.emit()
            self.close()
        else:
            QMessageBox.critical(self, "خطأ", msg)
            self.btn_login.setText("دخول 🚀")
            self.btn_login.setEnabled(True)

    def handle_signup(self):
        name = self.signup_name.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_pass.text().strip()
        profession = self.signup_profession.currentText()
        
        if not name or not email or not password or profession == "اختر المهنة...":
            QMessageBox.warning(self, "تنبيه", "يرجى ملء جميع الحقول واختيار المهنة.")
            return
            
        if not self.terms_checkbox.isChecked():
            QMessageBox.warning(self, "تنبيه", "يجب الموافقة على سياسة الخصوصية وحقوق الملكية للمتابعة.")
            return

        self.btn_signup.setText("جاري إنشاء الحساب...")
        self.btn_signup.setEnabled(False)

        success, msg = self.user_manager.register(name, email, password, profession)
        if success:
            QMessageBox.information(self, "نجاح", "تم إنشاء الحساب بنجاح!")
            self.auth_successful.emit()
            self.close()
        else:
            QMessageBox.critical(self, "خطأ", msg)
            self.btn_signup.setText("إنشاء الحساب 🌟")
            self.btn_signup.setEnabled(True)