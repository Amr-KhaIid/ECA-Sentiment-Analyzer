# ui/main_window.py
import re
import os
import random
import time
import requests
import zipfile
import io
import pandas as pd
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QLabel, QFrame, QProgressBar,
                             QDialog, QComboBox, QCheckBox, QMessageBox, QTabWidget, 
                             QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QSpinBox, QHeaderView, QScrollArea, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QTime, QDate
from PyQt6.QtGui import QFont, QPainter, QPageLayout
from PyQt6.QtPrintSupport import QPrinter

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import arabic_reshaper
from bidi.algorithm import get_display

from core.hybrid_analyzer import HybridPipeline
from database.cloud_memory import save_user_feedback, get_app_update_info
from data_processing.csv_handler import CSVHandler

def fix_arabic(text):
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

# ==========================================
# 1. خيوط المعالجة (Threads) 
# ==========================================
class AnalysisThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, pipeline, text):
        super().__init__()
        self.pipeline = pipeline
        self.text = text

    def run(self):
        try:
            result = self.pipeline.analyze(self.text)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class BatchAnalysisThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, handler, df):
        super().__init__()
        self.handler = handler
        self.df = df
        self._is_running = True

    def stop(self):
        self._is_running = False

    def check_stop(self):
        return not self._is_running

    def run(self):
        try:
            analyzed_df = self.handler.process_batch_dataframe(self.df, self.progress.emit, self.check_stop)
            self.finished.emit(analyzed_df)
        except Exception as e:
            self.error.emit(str(e))

#  خيط التحديث (OTA Updater Thread)
class ModelUpdateThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, download_url, extract_path):
        super().__init__()
        self.download_url = download_url
        self.extract_path = extract_path
        
    def run(self):
        try:
            #  وضع المحاكاة (Test Mode) لاختبار النظام
            if self.download_url == "test_mode":
                for i in range(1, 101):
                    time.sleep(0.03) # محاكاة التحميل
                    self.progress.emit(i)
                self.finished.emit(True, "تم تحميل وتثبيت الموديل بنجاح (وضع المحاكاة)! الموديل الآن محدث وجاهز للعمل.")
                return

            #  وضع التحميل الحقيقي للموديل
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            content = bytearray()
            
            for data in response.iter_content(chunk_size=8192):
                content.extend(data)
                downloaded += len(data)
                if total_size > 0:
                    p = int((downloaded / total_size) * 100)
                    self.progress.emit(p)
                    
            self.progress.emit(100)
            
            # فك الضغط الحقيقي واستبدال الملفات
            with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
                zip_ref.extractall(self.extract_path)
                
            self.finished.emit(True, "تم تحميل وتثبيت الموديل الجديد بنجاح! يرجى إعادة تشغيل البرنامج لتفعيل التحديثات.")
        except Exception as e:
            self.finished.emit(False, f"فشل التحديث: {str(e)}")

# ==========================================
# 2. الواجهة الرئيسية (Main Window)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.setWindowTitle("ECA Sentiment & XAI Enterprise")
        self.resize(1300, 900)
        
        self.total_ops_count = 0 
        self.current_user_name = "مستخدم"
        self.app_version = "V1.0 - Ultimate Champion" # الإصدار الحالي للبرنامج
        
        try:
            self.pipeline = HybridPipeline()
            self.csv_handler = CSVHandler(self.pipeline)
        except Exception as e:
            print(f"Error loading model: {e}")
            self.pipeline = None
            self.csv_handler = None

        self.master_df = None
        self.setup_ui()
        self.apply_styles()
        
        self.live_clock_timer = QTimer(self)
        self.live_clock_timer.timeout.connect(self.update_live_clock)
        self.live_clock_timer.start(1000)
        self.update_live_clock()

        self.greeting_timer = QTimer(self)
        self.greeting_timer.timeout.connect(self.update_greeting)
        self.greeting_timer.start(15 * 60 * 1000) 
        self.update_greeting()

    # ----------------------------------------------------
    # تحديثات الهيدر (الوقت، العمليات، والترحيب)
    # ----------------------------------------------------
    def update_live_clock(self):
        days_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        current_date = QDate.currentDate()
        current_time = QTime.currentTime()
        
        day_name = days_ar[current_date.dayOfWeek() - 1]
        time_str = current_time.toString("hh:mm:ss A").replace("AM", "ص").replace("PM", "م")
        
        self.day_label.setText(day_name)
        self.clock_label.setText(time_str)

    def update_greeting(self, custom_msg=None):
        if custom_msg:
            self.header_greeting.setText(custom_msg)
            return
            
        current_hour = QTime.currentTime().hour()
        
        if 5 <= current_hour < 12:
            msgs = [
                f"صباح الخير يا {self.current_user_name} ☀️، نتمنى لك بداية يوم موفقة!", 
                f"إشراقة صباح جديدة يا {self.current_user_name} ☕، جاهزين لتحليل البيانات؟",
                f"صباح الفل والياسمين يا {self.current_user_name} 🌸، يلا بينا نحلل شوية داتا؟",
                f"يا صباح الروقان ☕، الموديل جاهز ومستني أوامرك يا هندسة.",
                f"صباح النشاط يا بطل! 🚀 أنا شربت كوباية البيانات بتاعتي ومستعد.",
                f"صباح الخير! بصفتي ذكاء اصطناعي أنا مابنامش، بس حقيقي حاسس بنشاط الصبح معاك 🤖.",
                f"يا صباح الفل ☀️.. إيه رأيك نحلل كام ألف جملة قبل الفطار؟",
                f"صباح الخير يا {self.current_user_name}.. أنا جاهز أشتغل، بس أرجوك ماتطلبش مني أعد من واحد لمليون عالصبح كده!",
                f"يوم جديد، داتا جديدة، وتحديات نكسرها مع بعض يا {self.current_user_name} 💪",
                f"صباح السعادة 🌼.. المعالجات بتاعتي سخنت ومستنية تدوس على بدء التحليل."
            ]
        elif 12 <= current_hour < 18:
            msgs = [
                f"طاب مساؤك يا {self.current_user_name} 🌤️، وقت ممتاز للتدقيق والتحليل!", 
                f"أهلاً بك يا {self.current_user_name} في منصة ECA Sentiment Analyzer 📊.",
                f"مساء العظمة يا {self.current_user_name} 🚀، الداتا مابتستناش!",
                f"يا هلا بالباشمهندس {self.current_user_name} 💡، إيه الأخبار في الشغل النهاردة؟",
                f"منتصف اليوم هو وقت التألق ✨.. أنا كـ AI طاقتي 100%، وأنت؟",
                f"شغالين ولا ناخد بريك غدا؟ 🍔 أنا عن نفسي بتغدى أرقام وخوارزميات!",
                f"عاش يا {self.current_user_name}.. لو حاسس بكسل بعد الغدا سيبلي أنا التحليل وروح اعمل قهوة.",
                f"وقت العصرية ده محتاج شوية بيانات عامية مصرية نظبط بيهم المزاج 😎",
                f"أهلاً بك.. تفتكر هقدر أفهم السخرية في الداتا بتاعتك النهاردة؟ جربني ومش هتندم 🤖",
                f"مجهود عظيم لحد دلوقتي! لو احتجتني أعملك نكتة بالذكاء الاصطناعي أنا جاهز.. بس خلينا في الداتا أحسن."
            ]
        elif 18 <= current_hour < 23:
            msgs = [
                f"مساء الخير يا {self.current_user_name} 🌙، عساك بخير في هذا الوقت!", 
                f"أهلاً يا {self.current_user_name} ✨، نعمل بكفاءة حتى في المساء!",
                f"يا مساء الفل 🌙، كوباية الشاي الحلوة بتاعتك يا {self.current_user_name} وروّق على الداتا.",
                f"عاش يا {self.current_user_name} 💪، الموديل في ظهرك ومكملين للآخر.",
                f"المساء ده وقت الروقان والتفكير العميق.. وكمان وقت استخراج القواعد المعقدة ⚙️",
                f"لسه شغال يا بطل؟ أنا معاك للصبح، الكود بتاعي مابيتعبش 🦾",
                f"مساء السعادة 🌌.. إيه رأيك أخلي الذكاء الاصطناعي يعملك قهوة؟ للأسف أنا مجرد سوفتوير، فاعملها إنت!",
                f"الدنيا بتليل والهدوء بيزيد، وده أحسن وقت الـ GPU بتاعي بيشتغل فيه بمزاج 🚀",
                f"مساء الفل! أنا جاهز أحلل الداتا، بس لو لقيت الجمل كلها سلبية ماتزعلش، أنا مجرد مراية للبيانات 😅",
                f"يا هلا يا هلا.. خلصت شغل ولا لسه بنسخن؟ أنا كـ AI معنديش مواعيد انصراف للأسف!"
            ]
        else:
            msgs = [
                f"وقت متأخر يا {self.current_user_name} 🦉! لا تنسَ أخذ قسط من الراحة.", 
                f"نحييك على مجهودك في هذا الوقت المتأخر يا {self.current_user_name} ☕!",
                f"يا سهران ليالي الداتا 🦉، عاش جداً بس ماتنساش تنام شوية!",
                f"أبطال الداتا مابيناموش 🚀، بس خد بريك يا {self.current_user_name} عشان تركيزك.",
                f"بتعمل إيه صاحي لحد دلوقتي؟! روح نام وسيبلي أنا الكود.. آه صح أنا مقدرش أشتغل لوحدي 😅",
                f"الساعة عدت نص الليل.. أنا ممكن أعدلك من 1 لمليون عشان تنام، بس خايف أخلصهم في مللي ثانية وتفضل صاحي 🤖",
                f"سهرانين بنحلل داتا؟ 😉",
                f"الـ RAM بتاعتي صاحية ومصحصحة، بس الـ RAM بتاعتك محتاجة تنام يا هندسة 🧠💤",
                f"وحياة المازربورد بتاعتي إنت بطل إنك لسه شغال لحد دلوقتي! 💪",
                f"الذكاء الاصطناعي مابينامش، بس البشر بيحتاجوا.. خلص اللي بتعمله وافصل شحن بقى 🔋"
            ]

        self.header_greeting.setText(random.choice(msgs))

    def increment_ops(self, count=1):
        self.total_ops_count += count
        self.ops_count_label.setText(str(self.total_ops_count))

    # ----------------------------------------------------
    # بناء الواجهة
    # ----------------------------------------------------
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_header_frame = QFrame()
        top_header_frame.setObjectName("topHeaderFrame")
        top_header_layout = QHBoxLayout(top_header_frame)
        top_header_layout.setContentsMargins(15, 10, 15, 10)

        clock_layout = QHBoxLayout()
        self.day_label = QLabel("السبت")
        self.day_label.setObjectName("smallHeaderLabel")
        self.clock_label = QLabel("12:00:00 ص")
        self.clock_label.setObjectName("bigHeaderLabel")
        clock_layout.addWidget(self.day_label)
        clock_layout.addWidget(self.clock_label)
        clock_layout.addStretch()
        
        self.header_greeting = QLabel()
        self.header_greeting.setObjectName("greetingLabel")
        self.header_greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ops_layout = QHBoxLayout()
        ops_layout.addStretch()
        ops_title = QLabel("عملية ناجحة")
        ops_title.setObjectName("smallHeaderLabel")
        self.ops_count_label = QLabel("0")
        self.ops_count_label.setObjectName("opsCounterLabel")
        ops_layout.addWidget(ops_title)
        ops_layout.addWidget(self.ops_count_label)

        top_header_layout.addLayout(clock_layout)
        top_header_layout.addWidget(self.header_greeting, stretch=1)
        top_header_layout.addLayout(ops_layout)

        main_layout.addWidget(top_header_frame)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_single = QWidget()
        self.setup_single_tab()
        self.tabs.addTab(self.tab_single, "🔍 التحليل الفردي والتفسير")

        self.tab_batch = QWidget()
        self.setup_batch_tab()
        self.tabs.addTab(self.tab_batch, "📁 معالجة وتدقيق الملفات")

        self.tab_report = QWidget()
        self.setup_report_tab()
        self.tabs.addTab(self.tab_report, "📊 لوحة التحكم والتقارير")

        self.tab_about = QWidget()
        self.setup_about_tab()
        self.tabs.addTab(self.tab_about, "ℹ️ عن المشروع والخصوصية")

    # ----------------------------------------------------
    # Tab 1: التحليل الفردي
    # ----------------------------------------------------
    def setup_single_tab(self):
        layout = QVBoxLayout(self.tab_single)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("أدخل النص المراد تحليله هنا...")
        self.input_text.setFixedHeight(90)
        layout.addWidget(self.input_text)

        self.analyze_btn = QPushButton("تحليل وتفسير القرار 🚀")
        self.analyze_btn.setFixedHeight(45)
        self.analyze_btn.clicked.connect(self.start_analysis)
        layout.addWidget(self.analyze_btn)

        self.single_progress = QProgressBar()
        self.single_progress.setVisible(False)
        layout.addWidget(self.single_progress)

        pipeline_layout = QHBoxLayout()
        self.ai_model_card = self.create_card("🧠 قرار الموديل (MARBERT)", "---", "الكلمات المؤثرة: ---")
        pipeline_layout.addWidget(self.ai_model_card)

        self.rules_engine_card = self.create_card("⚙️ قرار محرك القواعد", "---", "المقاطع الملتقطة: ---")
        pipeline_layout.addWidget(self.rules_engine_card)

        layout.addLayout(pipeline_layout)

        self.final_decision_card = QFrame()
        self.final_decision_card.setObjectName("finalCard")
        final_layout = QVBoxLayout(self.final_decision_card)
        final_layout.setSpacing(2) 
        final_layout.setContentsMargins(5, 5, 5, 5)
        
        t_label = QLabel("🎯 القرار النهائي الهجين")
        t_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_label.setObjectName("cardTitle")
        
        self.final_val_label = QLabel("---")
        self.final_val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_val_label.setObjectName("cardValue")
        
        self.final_det_label = QLabel("")
        self.final_det_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_det_label.setWordWrap(True)
        self.final_det_label.setObjectName("finalCardDetails")

        self.edit_feedback_btn = QPushButton("✏️ تصحيح النتيجة (User Feedback)")
        self.edit_feedback_btn.setObjectName("editBtn")
        self.edit_feedback_btn.setFixedSize(200, 30)
        self.edit_feedback_btn.setEnabled(False)
        self.edit_feedback_btn.clicked.connect(self.open_edit_dialog)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.edit_feedback_btn)
        btn_layout.addStretch()

        final_layout.addWidget(t_label)
        final_layout.addWidget(self.final_val_label)
        final_layout.addWidget(self.final_det_label)
        final_layout.addLayout(btn_layout)

        layout.addWidget(self.final_decision_card)
        
        self.breakdown_box = QTextEdit()
        self.breakdown_box.setReadOnly(True)
        self.breakdown_box.setObjectName("breakdownBox")
        self.breakdown_box.setMinimumHeight(130) 
        self.breakdown_box.setMaximumHeight(150)
        layout.addWidget(self.breakdown_box)

    # ----------------------------------------------------
    # Tab 2: Batch Tab 
    # ----------------------------------------------------
    def setup_batch_tab(self):
        layout = QVBoxLayout(self.tab_batch)
        
        # شريط أدوات الجدول (استيراد وإضافة ومسح)
        tools_bar = QHBoxLayout()
        self.upload_btn = QPushButton("📁 استيراد ملف (CSV/Excel)")
        self.upload_btn.clicked.connect(self.select_file)
        
        self.add_row_btn = QPushButton("➕ إضافة صف")
        self.add_row_btn.clicked.connect(self.add_empty_row)
        
        self.del_row_btn = QPushButton("🗑️ مسح صف")
        self.del_row_btn.clicked.connect(self.delete_selected_row)
        
        tools_bar.addWidget(self.upload_btn)
        tools_bar.addWidget(self.add_row_btn)
        tools_bar.addWidget(self.del_row_btn)
        tools_bar.addStretch()
        layout.addLayout(tools_bar)

        # الجدول
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "النص (قابل للتعديل)", "النتيجة", "سخرية", "مصدر القرار", "القاعدة المفعلة", "ثقة AI", "انتباه AI", "كلمات قواعد"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # شريط خيارات المعالجة (تحديد النطاق وبدء التحليل)
        process_bar = QHBoxLayout()
        
        self.analyze_all_cb = QCheckBox("تحليل كل الصفوف")
        self.analyze_all_cb.setChecked(True)
        self.analyze_all_cb.stateChanged.connect(self.toggle_row_spinners)
        
        self.start_row_spin = QSpinBox()
        self.start_row_spin.setMinimum(1)
        self.start_row_spin.setEnabled(False)
        self.start_row_spin.setPrefix("من صف: ")
        
        self.end_row_spin = QSpinBox()
        self.end_row_spin.setMinimum(1)
        self.end_row_spin.setEnabled(False)
        self.end_row_spin.setPrefix("إلى صف: ")

        self.start_batch_btn = QPushButton("▶️ بدء التحليل المحدد")
        self.start_batch_btn.clicked.connect(self.start_batch_analysis)
        
        self.kill_btn = QPushButton("⏹️ إيقاف")
        self.kill_btn.setObjectName("killBtn")
        self.kill_btn.setEnabled(False)
        self.kill_btn.clicked.connect(self.kill_analysis)
        
        process_bar.addWidget(self.analyze_all_cb)
        process_bar.addWidget(self.start_row_spin)
        process_bar.addWidget(self.end_row_spin)
        process_bar.addStretch()
        process_bar.addWidget(self.start_batch_btn)
        process_bar.addWidget(self.kill_btn)
        layout.addLayout(process_bar)

        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        layout.addWidget(self.batch_progress)

        # شريط الفلاتر والتصدير
        filter_layout = QHBoxLayout()
        
        self.filter_source = QComboBox()
        self.filter_source.setMinimumWidth(140) # تحديد عرض أدنى
        self.filter_source.addItems(["الكل", "الذكاء الاصطناعي", "محرك القواعد", "السحابة (Feedback)"])
        
        self.filter_sentiment = QComboBox()
        self.filter_sentiment.setMinimumWidth(140) # تحديد عرض أدنى
        self.filter_sentiment.addItems(["الكل", "إيجابي", "سلبي", "محايد", "مشاعر مختلطة"])
        
        self.filter_rule = QComboBox()
        self.filter_rule.setMinimumWidth(180) # عرض أكبر شوية عشان يستوعب أسماء القواعد بعدين
        self.filter_rule.addItem("الكل")
        
        self.apply_filter_btn = QPushButton("🔍 تطبيق الفلتر")
        self.apply_filter_btn.clicked.connect(self.apply_filters)

        filter_layout.addWidget(QLabel("تصفية النتائج: "))
        filter_layout.addWidget(self.filter_source)
        filter_layout.addWidget(self.filter_sentiment)
        filter_layout.addWidget(self.filter_rule)
        filter_layout.addStretch()
        filter_layout.addWidget(self.apply_filter_btn)
        layout.addLayout(filter_layout)

        bottom_bar = QHBoxLayout()
        self.edit_row_btn = QPushButton("✏️ تصحيح الجملة المحددة (سحابة)")
        self.edit_row_btn.clicked.connect(self.edit_selected_row)
        self.edit_row_btn.setEnabled(False)
        
        self.export_btn = QPushButton("💾 تصدير (Export Excel)")
        self.export_btn.clicked.connect(self.export_data)
        
        bottom_bar.addWidget(self.edit_row_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.export_btn)
        layout.addLayout(bottom_bar)

        self.table.itemSelectionChanged.connect(lambda: self.edit_row_btn.setEnabled(len(self.table.selectedItems()) > 0))

    # ----------------------------------------------------
    # Tab 3: Dashboard & Reports 
    # ----------------------------------------------------
    def setup_report_tab(self):
        layout = QVBoxLayout(self.tab_report)
        
        kpi_layout = QHBoxLayout()
        self.kpi_total = self.create_kpi_card("إجمالي الجمل المجمعة", "0")
        self.kpi_f1 = self.create_kpi_card("F1-Score (تأثير النظام)", "0%")
        self.kpi_prec = self.create_kpi_card("Precision (الدقة)", "0%")
        self.kpi_rec = self.create_kpi_card("Recall (الاسترجاع)", "0%")
        
        kpi_layout.addWidget(self.kpi_total)
        kpi_layout.addWidget(self.kpi_f1)
        kpi_layout.addWidget(self.kpi_prec)
        kpi_layout.addWidget(self.kpi_rec)
        layout.addLayout(kpi_layout)

        self.figure = Figure(figsize=(12, 6), dpi=100)
        self.figure.patch.set_facecolor('#1e1e2e')
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        pdf_btn = QPushButton("📄 تصدير التقرير كـ PDF")
        pdf_btn.setObjectName("pdfBtn")
        pdf_btn.clicked.connect(self.export_report_pdf)
        layout.addWidget(pdf_btn)

    # ----------------------------------------------------
    # Tab 4: About the Project & OTA Updates 🌟
    # ----------------------------------------------------
    def setup_about_tab(self):
        main_layout = QVBoxLayout(self.tab_about)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #1e1e2e; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: #1e1e2e; }")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(20)

        title_label = QLabel("نظام التحليل الهجين للمشاعر في العامية المصرية (ECA Sentiment Analyzer)")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #cba6f7; font-size: 26px; font-weight: bold; margin-bottom: 10px;")
        scroll_layout.addWidget(title_label)

        def create_about_box(text):
            frame = QFrame()
            frame.setObjectName("aboutFrame")
            flayout = QVBoxLayout(frame)
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 16px; line-height: 1.6; color: #cdd6f4;")
            flayout.addWidget(lbl)
            return frame

        scroll_layout.addWidget(create_about_box(
            "🎓 <b>الهدف والفريق الأكاديمي:</b><br><br>"
            "يهدف هذا المشروع إلى خدمة وتطوير مجال اللسانيات الحاسوبية (Computational Linguistics).<br>"
            "تم تصميم وتطوير هذا النظام كمشروع تخرج بواسطة الطالب: <b>عمرو خالد عبد العظيم</b>.<br>"
            "تحت إشراف رئيس قسم الصوتيات واللسانيات بجامعة الإسكندرية - كلية الآداب، أستاذ دكتور <b>سامح الأنصاري</b>."
        ))

        scroll_layout.addWidget(create_about_box(
            "🔒 <b>أمان البيانات وسياسة الخصوصية:</b><br><br>"
            "البيانات اللي بتتاخد هي بس الجمل اللي هيعدلها المستخدم، عشان كل فترة نعمل بيها Fine-tuning للموديل ونحسن من جودة إجاباته.<br>"
            "بيانات المستخدمين اللي بيتم تحليلها بتكون على أجهزتهم، ومبنشوفهاش أو نجمعها، وحقوقهم محفوظة تماماً."
        ))

        scroll_layout.addWidget(create_about_box(
            "⚖️ <b>حقوق الملكية والاستخدام:</b><br><br>"
            "استخدام المنتج أو البرنامج مجاني تماماً وموجه لطلبة الصوتيات وكل من يهمه أمر تحليل اللغة وخصوصاً إيجاد قطبية المشاعر في العامية المصرية، أياً كان غرضه (تجارياً أم تجريبياً ودراسياً).<br>"
            "<b>بشرط:</b> توضيح الفائدة التي عمّ عليها المشروع على برنامجه أو مجال دراستك."
        ))

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area) 

        # 🌟 زرار البحث عن التحديثات الفعلي (OTA Update)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(30, 10, 30, 20)
        
        self.update_model_btn = QPushButton("🔄 البحث عن تحديثات للموديل (Check for Updates)")
        self.update_model_btn.setFixedHeight(65)
        self.update_model_btn.setObjectName("updateBtn")
        self.update_model_btn.clicked.connect(self.check_model_updates)
        
        btn_layout.addWidget(self.update_model_btn)
        main_layout.addLayout(btn_layout)

    def check_model_updates(self):
        """التحقق من وجود تحديثات للموديل عبر السحابة"""
        self.update_model_btn.setEnabled(False)
        self.update_model_btn.setText("جاري الاتصال بالسيرفر والبحث... ⏳")
        
        update_info = get_app_update_info()
        
        self.update_model_btn.setEnabled(True)
        self.update_model_btn.setText("🔄 البحث عن تحديثات للموديل (Check for Updates)")
        
        if not update_info:
            QMessageBox.warning(self, "خطأ", "لم نتمكن من الاتصال بخادم التحديثات. تأكد من اتصالك بالإنترنت.")
            return
            
        latest_version = update_info.get("latest_version", self.app_version)
        download_url = update_info.get("download_url", "")
        release_notes = update_info.get("release_notes", "لا توجد تفاصيل إضافية.")
        
        if latest_version != self.app_version:
            reply = QMessageBox.question(
                self, 
                "تحديث جديد متاح! 🎉", 
                f"إصدار جديد متاح: {latest_version}\n\n"
                f"التحديثات الجديدة:\n{release_notes}\n\n"
                "هل تريد تحميل وتثبيت التحديث الآن؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.start_model_download(download_url)
        else:
            QMessageBox.information(
                self, "تحديث الموديل", 
                "أنت تستخدم أحدث إصدار من الموديل بالفعل!\nلا توجد تحديثات متاحة حالياً."
            )

    def start_model_download(self, url):
        """بدء نافذة التحميل واستدعاء خيط التحديث"""
        self.progress_dialog = QProgressDialog("جاري تحميل وتثبيت الموديل الجديد...", "إلغاء", 0, 100, self)
        self.progress_dialog.setWindowTitle("تحديث النظام")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setStyleSheet("QProgressDialog { background-color: #1e1e2e; color: #cdd6f4;} QLabel{color: #cdd6f4;} QPushButton{background-color: #f38ba8;}")
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.show()
        
        # استخراج مسار مجلد الموديلات
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        extract_path = os.path.join(base_dir, "models", "Active_Model")
        
        self.update_thread = ModelUpdateThread(url, extract_path)
        self.update_thread.progress.connect(self.progress_dialog.setValue)
        self.update_thread.finished.connect(self.on_update_finished)
        self.update_thread.start()
        
    def on_update_finished(self, success, message):
        if success:
            QMessageBox.information(self, "نجاح التحديث", message)
            self.app_version = "V1.1 - Super Champion" # تحديث الإصدار محلياً
        else:
            QMessageBox.critical(self, "فشل التحديث", message)

    # ==========================================
    # Helper Functions
    # ==========================================
    def create_card(self, title, value, details):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setObjectName("resultCard")
        layout = QVBoxLayout(frame)
        t_label = QLabel(title)
        t_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_label.setObjectName("cardTitle")
        v_label = QLabel(value)
        v_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_label.setObjectName("cardValue")
        d_label = QLabel(details)
        d_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d_label.setWordWrap(True)
        d_label.setObjectName("cardDetails")
        layout.addWidget(t_label)
        layout.addWidget(v_label)
        layout.addWidget(d_label)
        frame.value_label = v_label
        frame.details_label = d_label
        return frame

    def create_kpi_card(self, title, value):
        frame = QFrame()
        frame.setObjectName("kpiCard")
        frame.setMinimumHeight(110) # 👈 إجبار الواجهة إن الكارت ما يقلش عن الحجم ده
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 15, 10, 15) # 👈 مسافات داخلية (هوامش) عشان الكلام ميتلصقش في الحواف
        layout.setSpacing(10) # 👈 مسافة بين العنوان والرقم
        
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("color: #bac2de; font-size: 15px; font-weight: bold;") # تكبير خط العنوان شوية
        
        v = QLabel(value)
        v.setObjectName("kpiValue")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(t)
        layout.addWidget(v)
        frame.val_label = v
        return frame

    def generate_segment_breakdown(self, raw_text, lex_pos, lex_neg, segments):
        clauses = re.split(r'(?:،|بس\b|لكن\b|رغم\b|مع ان\b|؛|\.|!|\?)', raw_text)
        html = "<ul style='margin-top: 5px; margin-bottom: 5px; padding-right: 20px;'>" 
        for clause in clauses:
            clause_clean = clause.strip()
            if not clause_clean: continue
            
            clause_pos = [w for w in lex_pos if w in clause_clean]
            clause_neg = [w for w in lex_neg if w in clause_clean]
            clause_rules = [s for s in segments if s in clause_clean]
            
            if clause_pos and not clause_neg: status = f"<span style='color:#a6e3a1;'>[جزء إيجابي 🟢 بسبب: {', '.join(clause_pos)}]</span>"
            elif clause_neg and not clause_pos: status = f"<span style='color:#f38ba8;'>[جزء سلبي 🔴 بسبب: {', '.join(clause_neg)}]</span>"
            elif clause_pos and clause_neg: status = f"<span style='color:#cba6f7;'>[تضارب ⚖️ بسبب: {', '.join(clause_pos + clause_neg)}]</span>"
            elif clause_rules: status = f"<span style='color:#f9e2af;'>[تدخل قواعد ⚠️ بسبب: {', '.join(clause_rules)}]</span>"
            else: status = "<span style='color:#bac2de;'>[جزء سياقي ⚪]</span>"
                
            html += f"<li style='margin-bottom: 5px;'><b>{clause_clean}</b> {status}</li>"
        html += "</ul>"
        return html

   # ==========================================
    # Logic: Batch Processing & Threads
    # ==========================================
    
    # دوال مساعدة للتحكم في الجدول (إضافة، مسح، تحديد النطاق)
    def add_empty_row(self):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        item = QTableWidgetItem("")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row_count, 0, item)
        self.update_spinners_max()

    def delete_selected_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.update_spinners_max()

    def toggle_row_spinners(self):
        is_checked = self.analyze_all_cb.isChecked()
        self.start_row_spin.setEnabled(not is_checked)
        self.end_row_spin.setEnabled(not is_checked)

    def update_spinners_max(self):
        count = max(1, self.table.rowCount())
        self.start_row_spin.setMaximum(count)
        self.end_row_spin.setMaximum(count)
        if self.end_row_spin.value() < self.start_row_spin.value() or self.analyze_all_cb.isChecked():
            self.end_row_spin.setValue(count)

    # دوال التحليل ومعالجة الملفات
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختر الملف", "", "Data Files (*.csv *.xlsx)")
        if path:
            try:
                # نقرأ الملف ونحطه في الجدول أولاً (العمود الأول فقط)
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
                self.table.setRowCount(0)
                if not df.empty:
                    self.table.setRowCount(len(df))
                    text_col = df.columns[0]
                    for row_idx, text in enumerate(df[text_col]):
                        item = QTableWidgetItem(str(text))
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable) # نجعل النص قابل للتعديل
                        self.table.setItem(row_idx, 0, item)
                    self.update_spinners_max()
                    self.start_batch_btn.setEnabled(True)
                    QMessageBox.information(self, "تم", "تم تحميل البيانات في الجدول بنجاح، يمكنك تصفحها وتعديلها الآن قبل التحليل.")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء قراءة الملف: {str(e)}")

    def start_batch_analysis(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "تنبيه", "لا توجد بيانات للتحليل. قم بإضافة صفوف أو استيراد ملف.")
            return

        data_to_analyze = []
        
        # تحديد النطاق اللي هيتحلل (الكل أو من كذا لكذا)
        if hasattr(self, 'analyze_all_cb') and self.analyze_all_cb.isChecked():
            start_idx = 0
            end_idx = self.table.rowCount()
        else:
            start_idx = self.start_row_spin.value() - 1
            end_idx = self.end_row_spin.value()
            if start_idx > end_idx or start_idx < 0:
                QMessageBox.warning(self, "خطأ", "النطاق المحدد غير صحيح.")
                return

        # جمع النصوص من الجدول لتكوين Dataframe
        for row in range(start_idx, end_idx):
            item = self.table.item(row, 0)
            if item and item.text().strip():
                data_to_analyze.append({"النص الأصلي": item.text().strip()})

        if not data_to_analyze:
             QMessageBox.warning(self, "تنبيه", "الصفوف المحددة فارغة.")
             return

        df_to_analyze = pd.DataFrame(data_to_analyze)

        self.start_batch_btn.setEnabled(False)
        self.kill_btn.setEnabled(True)
        self.batch_progress.setVisible(True)
        self.batch_progress.setValue(0)
        
        batch_msgs = [
            "☕ روح اعمل قهوتك بمزاج.. واحنا هنخلص تحليل الملف ونجهزلّك التقرير!",
            "🚀 جاري طحن البيانات! لو الملف كبير، روح اتفرج على حلقة من مسلسلك المفضل لحد ما أخلص.",
            "📊 بدأنا عملية التحليل والتدقيق الشامل للبيانات.. يرجى الانتظار.",
            f"🎓 جاري تحليل الصفوف المحددة يا {self.current_user_name}..."
        ]
        self.update_greeting(random.choice(batch_msgs))
        
        self.batch_thread = BatchAnalysisThread(self.csv_handler, df_to_analyze)
        self.batch_thread.progress.connect(self.batch_progress.setValue)
        # نمرر start_idx عشان نعرف هنحط النتايج فين في الجدول بالظبط
        self.batch_thread.finished.connect(lambda df: self.batch_analysis_done(df, start_idx))
        self.batch_thread.error.connect(lambda e: QMessageBox.critical(self, "خطأ", e))
        self.batch_thread.start()

    def kill_analysis(self):
        if hasattr(self, 'batch_thread'):
            self.batch_thread.stop()
            self.kill_btn.setEnabled(False)
            QMessageBox.warning(self, "توقف", "تم تفعيل الـ Kill Switch! تم إيقاف المعالجة. سيتم عرض ما تم إنجازه.")

    def batch_analysis_done(self, df, start_idx_in_table):
        self.kill_btn.setEnabled(False)
        self.start_batch_btn.setEnabled(True)
        self.batch_progress.setVisible(False)
        self.export_btn.setEnabled(True)
        
        self.update_greeting()
        
        # حفظ النتايج في الماستر داتا فريم للداشبورد
        if getattr(self, 'master_df', None) is None or self.master_df.empty:
            self.master_df = df
        else:
            self.master_df = pd.concat([self.master_df, df], ignore_index=True)
            
        self.increment_ops(len(df))
        
        # وضع النتائج في الجدول بجانب النصوص، بداية من الصف اللي تم تحديده
        for i, row in df.iterrows():
            table_row = start_idx_in_table + i
            cols_data = [
                row["النص الأصلي"], row["النتيجة النهائية"], row["السخرية"], 
                row["مصدر القرار"], row["القاعدة المفعلة"], str(row["ثقة الذكاء الاصطناعي (%)"]), 
                row["انتباه AI"], row["كلمات القواعد"]
            ]
            for col_idx, val in enumerate(cols_data):
                if col_idx == 0: continue # بنتجاهل العمود الأول لأنه مكتوب أصلاً
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(table_row, col_idx, item)
        
        unique_rules = set()
        for r in self.master_df["القاعدة المفعلة"]:
            if r != "لا يوجد": unique_rules.update(r.split("، "))
        self.filter_rule.clear()
        self.filter_rule.addItem("الكل")
        self.filter_rule.addItems(list(unique_rules))
        
        self.refresh_dashboard()
        QMessageBox.information(self, "نجاح", "تمت معالجة البيانات بنجاح! راجع الجدول والتقارير.")

    def apply_filters(self):
        if not hasattr(self, 'master_df') or self.master_df is None: return
        filtered_df = self.csv_handler.filter_dataframe(
            self.master_df,
            self.filter_source.currentText(),
            self.filter_rule.currentText(),
            self.filter_ai_conf.value() if hasattr(self, 'filter_ai_conf') else 100,
            self.filter_sentiment.currentText()
        )
        self.table.setRowCount(0)
        if filtered_df is None or filtered_df.empty: return
        self.table.setRowCount(len(filtered_df))
        for row_idx, (_, row) in enumerate(filtered_df.iterrows()):
            cols = [
                row["النص الأصلي"], row["النتيجة النهائية"], row["السخرية"], 
                row["مصدر القرار"], row["القاعدة المفعلة"], str(row["ثقة الذكاء الاصطناعي (%)"]), 
                row["انتباه AI"], row["كلمات القواعد"]
            ]
            for c_idx, val in enumerate(cols):
                it = QTableWidgetItem(str(val))
                if c_idx != 0: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, c_idx, it)

    # ==========================================
    # Logic: Single Analysis 
    # ==========================================
    def open_edit_dialog(self):
        text = self.input_text.toPlainText().strip()
        if not text: return
        dialog = QDialog(self)
        dialog.setWindowTitle("تعديل النتيجة - Feedback")
        dialog.setFixedSize(350, 200)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("اختر التقييم الصحيح للجملة:"))
        combo = QComboBox()
        combo.addItems(["إيجابي", "سلبي", "محايد", "مشاعر مختلطة"])
        current_val = self.final_val_label.text()
        if current_val in ["إيجابي", "سلبي", "محايد", "مشاعر مختلطة"]:
            combo.setCurrentText(current_val)
        layout.addWidget(combo)

        sarcasm_check = QCheckBox("يوجد سخرية في الجملة؟ (Sarcasm)")
        layout.addWidget(sarcasm_check)

        save_btn = QPushButton("حفظ ورفع للسحابة ☁️")
        layout.addWidget(save_btn)

        def perform_save():
            new_sentiment = combo.currentText()
            is_sarcasm = sarcasm_check.isChecked()
            save_btn.setText("جاري الرفع...")
            save_btn.setEnabled(False)
            
            # 👈 جلب النتيجة اللي حفظناها، ولو مش موجودة نكتب "غير معروف"
            ai_pred_to_save = getattr(self, 'last_ai_prediction', 'غير معروف')
            
            if save_user_feedback(text, ai_pred_to_save, new_sentiment, is_sarcasm):
                self.pipeline.user_feedback_cache[text] = {'sentiment': new_sentiment, 'sarcasm': is_sarcasm}
                QMessageBox.information(dialog, "تم بنجاح", "تم حفظ النتيجة بالسحابة! سيتم إعادة التحليل.")
                dialog.accept()
                self.start_analysis()
            else:
                QMessageBox.critical(dialog, "خطأ", "فشل الاتصال بقاعدة البيانات.")
                save_btn.setText("حفظ ورفع للسحابة ☁️")
                save_btn.setEnabled(True)

        save_btn.clicked.connect(perform_save)
        dialog.setStyleSheet("""QDialog { background-color: #1e1e2e; } QLabel { color: #cdd6f4; font-weight: bold;} QComboBox { background-color: #313244; color: white; border-radius: 5px;} QCheckBox { color: #cdd6f4;} QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 5px; padding: 8px;}""")
        dialog.exec()

    def edit_selected_row(self):
        row_idx = self.table.currentRow()
        if row_idx < 0: return
        
        original_text = self.table.item(row_idx, 0).text()
        current_sentiment = self.table.item(row_idx, 1).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("تصحيح السحابة (Feedback)")
        dialog.setFixedSize(350, 200)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"النص: {original_text[:30]}..."))
        combo = QComboBox()
        combo.addItems(["إيجابي", "سلبي", "محايد", "مشاعر مختلطة"])
        combo.setCurrentText(current_sentiment)
        layout.addWidget(combo)

        sarc_cb = QCheckBox("يوجد سخرية")
        layout.addWidget(sarc_cb)

        save_btn = QPushButton("تأكيد ورفع")
        layout.addWidget(save_btn)

        def save_and_update():
            new_sent = combo.currentText()
            is_sarc = sarc_cb.isChecked()
            
            # محاولة جلب نتيجة الموديل الأصلية من الجدول لو أمكن
            ai_pred_batch = "غير معروف"
            if 'نتيجة الذكاء الاصطناعي' in self.master_df.columns:
                idx = self.master_df.index[self.master_df['النص الأصلي'] == original_text].tolist()[0]
                ai_pred_batch = self.master_df.at[idx, 'نتيجة الذكاء الاصطناعي']
                
            # 👈 تم إضافة المتغير ai_pred_batch هنا
            if save_user_feedback(original_text, ai_pred_batch, new_sent, is_sarc):
                self.pipeline.user_feedback_cache[original_text] = {'sentiment': new_sent, 'sarcasm': is_sarc}
                
                idx = self.master_df.index[self.master_df['النص الأصلي'] == original_text].tolist()[0]
                self.master_df.at[idx, 'النتيجة النهائية'] = new_sent
                self.master_df.at[idx, 'السخرية'] = "نعم" if is_sarc else "لا"
                self.master_df.at[idx, 'مصدر القرار'] = "السحابة (Feedback)"
                self.master_df.at[idx, 'القاعدة المفعلة'] = "استرجاع نتيجة من الـ User Feedback Database ☁️"
                
                self.apply_filters()
                self.refresh_dashboard()
                QMessageBox.information(dialog, "نجاح", "تم الحفظ بالسحابة وتحديث البيانات!")
                dialog.accept()
            else:
                QMessageBox.critical(dialog, "خطأ", "فشل الحفظ في السحابة!")

        save_btn.clicked.connect(save_and_update)
        dialog.setStyleSheet("""QDialog {background-color: #1e1e2e; color:white;} QPushButton{background-color:#a6e3a1; color:black;} QComboBox{background-color:#313244; color:white;}""")
        dialog.exec()

    def start_analysis(self):
        text = self.input_text.toPlainText().strip()
        if not text or not self.pipeline: return
        self.analyze_btn.setEnabled(False)
        self.edit_feedback_btn.setEnabled(False)
        self.single_progress.setRange(0, 0)
        self.single_progress.setVisible(True)
        self.thread = AnalysisThread(self.pipeline, text)
        self.thread.finished.connect(self.display_results)
        self.thread.error.connect(self.handle_error)
        self.thread.start()

    def display_results(self, result):
        self.single_progress.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.edit_feedback_btn.setEnabled(True)

        self.increment_ops(1)

        ai_pred = result.get('dl_original_prediction', 'خطأ')
        self.last_ai_prediction = ai_pred  # 👈 السطر الجديد لحفظ النتيجة
        
        ai_conf = result.get('dl_confidence', 0)
        top_weights_list = result.get('top_ai_weights', [])
        top_words_str = "، ".join([f"{w} ({weight}%)" for w, weight in top_weights_list])
        
        self.ai_model_card.value_label.setText(f"{ai_pred} ({ai_conf}%)")
        self.ai_model_card.details_label.setText(f"أوزان الكلمات: [ {top_words_str if top_words_str else 'غير متاح'} ]")

        segments = result.get('matched_segments', [])
        lex_pos = result.get('lexicon_pos_words', [])
        lex_neg = result.get('lexicon_neg_words', [])
        
        rule_desc = f"مقاطع القواعد: [ {'، '.join(segments) if segments else 'لا يوجد'} ]"
        if lex_pos or lex_neg:
            rule_desc += f"\nمفردات القاموس: (+ {'، '.join(lex_pos)}) (- {'، '.join(lex_neg)})"
            
        self.rules_engine_card.value_label.setText("تم التدخل ⚠️" if (segments or (lex_pos and lex_neg)) else "لا توجد تعديلات")
        self.rules_engine_card.details_label.setText(rule_desc)

        final_sent = result.get("final_sentiment", "---")
        self.final_val_label.setText(final_sent)

        color = "#a6e3a1" 
        if final_sent == "سلبي": color = "#f38ba8" 
        elif final_sent == "محايد": color = "#f9e2af" 
        elif final_sent == "مشاعر مختلطة": color = "#cba6f7"
        self.final_val_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        
        rules_triggered = " | ".join(result.get("triggered_rules", [])) if result.get("triggered_rules") else "لم يتم تفعيل أي قواعد استثنائية."
        
        if "User Feedback Database" in rules_triggered:
            self.final_det_label.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 13px;")
        else:
            self.final_det_label.setStyleSheet("color: #f9e2af; font-style: italic; font-size: 12px;")
            
        self.final_det_label.setText(f"الأسباب: {rules_triggered}")

        segments_html = self.generate_segment_breakdown(result['original_text'], lex_pos, lex_neg, segments)
        breakdown_html = f"<h3 style='color: #89b4fa; margin:0px; font-size: 14px;'>📊 تحليل الأجزاء التفصيلي:</h3>{segments_html}<h3 style='color: #f9e2af; margin-top: 5px; font-size: 14px;'>🧠 أوزان انتباه الموديل (AI Attention):</h3><p style='color: #cdd6f4; font-size: 13px;'>الموديل ركز بنسبة كبيرة على: <b>{top_words_str if top_words_str else 'غير متاح'}</b></p>"
        self.breakdown_box.setHtml(breakdown_html)

    def handle_error(self, err_msg):
        self.single_progress.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.final_det_label.setText(f"حدث خطأ: {err_msg}")

    # ==========================================
    # Logic: Dashboard & Charts rendering
    # ==========================================
    def refresh_dashboard(self):
        metrics = self.csv_handler.calculate_dashboard_metrics(self.master_df)
        if not metrics: return

        # تحديث أرقام الـ KPIs
        self.kpi_total.val_label.setText(str(metrics["total_records"]))
        self.kpi_f1.val_label.setText(f"{metrics['f1_score']}%")
        self.kpi_prec.val_label.setText(f"{metrics['precision']}%")
        self.kpi_rec.val_label.setText(f"{metrics['recall']}%")

        self.figure.clear()
        
        text_color = '#cdd6f4'
        color_map = {
            "إيجابي": "#a6e3a1",
            "سلبي": "#f38ba8",
            "محايد": "#f9e2af",
            "مشاعر مختلطة": "#cba6f7"
        }

        # تقسيم المساحة لـ 4 رسومات (2 فوق و 2 تحت) لمساحة أوضح
        ax1 = self.figure.add_subplot(221) # توزيع المشاعر (Pie)
        ax2 = self.figure.add_subplot(222) # مصادر القرار (Horizontal Bar)
        ax3 = self.figure.add_subplot(223) # أكثر القواعد تدخلاً (Horizontal Bar)
        ax4 = self.figure.add_subplot(224) # تحليل السخرية (Bar)

        # --- 1. رسمة توزيع المشاعر (Donut Chart المعدلة) ---
        sent_data = metrics["sentiment_counts"]
        if sent_data:
            sent_labels = [fix_arabic(k) for k in sent_data.keys()]
            sent_colors = [color_map.get(k, "#bac2de") for k in sent_data.keys()]
            
            # pctdistance=1.2 بتخلي النسبة تطلع بره الدائرة
            # labeldistance=1.4 بتخلي النص (الكلمة) تطلع بره أكتر
            patches, texts, autotexts = ax1.pie(
                sent_data.values(), 
                labels=sent_labels, 
                autopct='%1.1f%%', 
                colors=sent_colors, 
                startangle=140,
                pctdistance=1.2, 
                labeldistance=1.5,
                wedgeprops=dict(width=0.4, edgecolor='#1e1e2e', linewidth=2)
            )
            
            # تنسيق الكلمات (labels)
            for t in texts:
                t.set_color(text_color)
                t.set_fontsize(11)
                t.set_weight('bold')
                
            # تنسيق الأرقام (autopct)
            for at in autotexts:
                at.set_color(text_color)
                at.set_weight('bold')
                at.set_fontsize(10)
                
            ax1.set_title(fix_arabic("توزيع المشاعر النهائية"), color=text_color, pad=20, weight='bold')

        # --- 2. رسمة مصادر اتخاذ القرار (Horizontal Bar Chart) ---
        src_data = metrics["source_counts"]
        if src_data:
            src_labels = [fix_arabic(k) for k in src_data.keys()]
            # رسم أفقي لسهولة قراءة النصوص العربية الطويلة
            bars2 = ax2.barh(src_labels, list(src_data.values()), color=['#89b4fa', '#f5c2e7', '#94e2d5'])
            ax2.set_title(fix_arabic("مصادر اتخاذ القرار (السيطرة)"), color=text_color, pad=15, weight='bold')
            ax2.tick_params(colors=text_color)
            # إضافة الأرقام على العواميد
            ax2.bar_label(bars2, padding=5, color=text_color, fontsize=11, weight='bold')
            # إخفاء الخطوط الجانبية لتنظيف الشكل
            ax2.spines['right'].set_visible(False)
            ax2.spines['top'].set_visible(False)

        # --- 3. رسمة أكثر القواعد تدخلاً (Horizontal Bar Chart) ---
        rule_data = metrics["rule_types_counts"]
        if rule_data:
            # ترتيب القواعد واختيار أعلى 5 فقط
            top_rules = dict(sorted(rule_data.items(), key=lambda item: item[1], reverse=True)[:5])
            top_rules_keys = list(top_rules.keys())[::-1]
            top_rules_vals = list(top_rules.values())[::-1]
            
            # تقصير الأسماء الطويلة عشان الرسمة ماتنضغطش
            short_labels = []
            for k in top_rules_keys:
                clean_name = str(k)
                if len(clean_name) > 28:
                    clean_name = clean_name[:28] + "..."
                short_labels.append(fix_arabic(clean_name))
                
            bars3 = ax3.barh(short_labels, top_rules_vals, color='#f5e0dc')
            ax3.set_title(fix_arabic("أكثر القواعد تدخلاً لتصحيح الموديل"), color=text_color, pad=15, weight='bold')
            ax3.tick_params(colors=text_color)
            ax3.bar_label(bars3, padding=5, color=text_color, fontsize=11, weight='bold')
            ax3.spines['right'].set_visible(False)
            ax3.spines['top'].set_visible(False)

        # --- 4. رسمة معدل اكتشاف السخرية (Vertical Bar Chart) ---
        if "السخرية" in self.master_df.columns:
            sarcasm_counts = self.master_df["السخرية"].value_counts().to_dict()
            sarc_labels = [fix_arabic(f"سخرية: {k}") for k in sarcasm_counts.keys()]
            bars4 = ax4.bar(sarc_labels, list(sarcasm_counts.values()), color=['#a6e3a1', '#f38ba8'], width=0.5)
            ax4.set_title(fix_arabic("معدلات اكتشاف السخرية بالتراكيب"), color=text_color, pad=15, weight='bold')
            ax4.tick_params(colors=text_color)
            ax4.bar_label(bars4, padding=3, color=text_color, fontsize=11, weight='bold')
            ax4.spines['right'].set_visible(False)
            ax4.spines['top'].set_visible(False)

        # تظبيط المسافات بين الرسومات بشكل أفضل (امسح subplots_adjust القديمة)
        self.figure.tight_layout(pad=3.0, w_pad=3.0, h_pad=3.0)
        
        # تلوين خلفية كل رسمة لتتناسب مع الـ Dark Theme
        for ax in [ax1, ax2, ax3, ax4]:
            ax.set_facecolor('#1e1e2e')
            for spine in ax.spines.values(): 
                spine.set_edgecolor('#45475a')

        self.canvas.draw()

        self.canvas.draw()
    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التقرير", "Exported_Data.xlsx", "Excel Files (*.xlsx)")
        if path:
            if hasattr(self, 'master_df') and self.master_df is not None and not self.master_df.empty:
                if self.csv_handler.export_to_excel(self.master_df, path):
                    QMessageBox.information(self, "نجاح", "تم حفظ الملف بنجاح!")
            else:
                QMessageBox.warning(self, "تنبيه", "لا توجد بيانات لتصديرها. قم بتحليل البيانات أولاً.")

    def export_report_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التقرير كـ PDF", "Dashboard_Report.pdf", "PDF Files (*.pdf)")
        if path:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
            
            pixmap = self.tab_report.grab()
            painter = QPainter(printer)
            
            rect = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
            scaled_pixmap = pixmap.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = int((rect.width() - scaled_pixmap.width()) / 2)
            y = int((rect.height() - scaled_pixmap.height()) / 2)
            
            painter.drawPixmap(x, y, scaled_pixmap)
            painter.end()
            
            QMessageBox.information(self, "نجاح", "تم تصدير تقرير لوحة التحكم كـ PDF بنجاح!")
    # ==========================================
    # Styles
    # ==========================================
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; color: #cdd6f4;}
            
            #topHeaderFrame { background-color: #181825; border-bottom: 2px solid #313244;}
            #greetingLabel { color: #cba6f7; font-size: 22px; font-weight: bold; }
            #smallHeaderLabel { color: #bac2de; font-size: 14px; font-weight: bold; }
            #bigHeaderLabel { color: #89b4fa; font-size: 20px; font-weight: bold; }
            #opsCounterLabel { color: #a6e3a1; font-size: 20px; font-weight: bold; }
            
            QLabel { color: #cdd6f4; font-size: 14px; font-weight: bold;}
            QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 8px; font-size: 14px; font-weight: bold; padding: 10px;}
            QPushButton:hover { background-color: #b4befe; }
            QPushButton:disabled { background-color: #45475a; color: #a6adc8; }
            
            #killBtn { background-color: #f38ba8; } #killBtn:hover { background-color: #eba0ac; }
            #pdfBtn { background-color: #f5c2e7; margin: 15px;}
            #updateBtn { background-color: #fab387; color: #11111b; font-size: 16px; border-radius: 10px; margin-top: 20px;}
            #updateBtn:hover { background-color: #f9e2af; }
            
            QComboBox, QSpinBox { background-color: #313244; color: white; padding: 5px; border-radius: 5px; }
            QTableWidget { background-color: #181825; color: #cdd6f4; gridline-color: #45475a; font-size: 13px;}
            QHeaderView::section { background-color: #313244; color: white; font-weight: bold; padding: 4px; border: 1px solid #45475a;}
            
            QTabWidget::pane { border: 2px solid #45475a; border-radius: 10px; background-color: #1e1e2e; padding: 10px; top: -1px;}
            QTabBar::tab { background-color: #313244; color: #cdd6f4; padding: 12px 30px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-left: 2px; font-size: 16px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #89b4fa; color: #11111b; }
            
            #kpiCard { background-color: #313244; border-radius: 10px; border: 2px solid #89b4fa; padding: 10px;}
            #kpiValue { color: #a6e3a1; font-size: 18px; font-weight: bold;}
            
            #resultCard { background-color: #313244; border: 2px solid #45475a; border-radius: 15px; min-height: 90px; }
            #finalCard { background-color: #181825; border: 3px solid #89b4fa; border-radius: 15px; min-height: 80px; margin-top: 5px;}
            #cardTitle { color: #bac2de; font-size: 13px; padding-top: 2px; }
            
            #aboutFrame { background-color: #181825; border: 1px solid #45475a; border-radius: 10px; padding: 15px; }
            
            QToolTip { color: #11111b; background-color: #f9e2af; border: 1px solid #cba6f7; border-radius: 4px; padding: 5px; font-size: 13px; font-weight:bold; }
        """)