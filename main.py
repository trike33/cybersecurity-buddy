import sys
import random
import os
import glob
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QDialog, 
                             QVBoxLayout, QLabel, QPushButton, QWidget, 
                             QHBoxLayout, QStackedWidget, QFrame, QAction,
                             QFileDialog, QMessageBox, QListWidget, QLineEdit,
                             QComboBox, QDateEdit, QTextEdit, QDialogButtonBox)
from PyQt5.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QPoint, QDate
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap
import shutil

# Import utilities
from utils import db as command_db
from utils import project_db

# ... (SimpleTextEditorDialog & StartupWizard classes remain unchanged) ...
class SimpleTextEditorDialog(QDialog):
    """A simple popup to let the user type in domains or scope IPs manually."""
    def __init__(self, title, current_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Enter content (one per line):")
        layout.addWidget(lbl)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(current_text)
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_text(self):
        return self.text_edit.toPlainText()

# ---------------------------------------------------------
# 1. INTEGRATED SLIDING WIZARD
# ---------------------------------------------------------
class StartupWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyberSec Buddy - Launcher")
        self.setFixedSize(1200, 900)

        # --- RANDOM WALLPAPER LOGIC ---
        base_path = os.path.dirname(os.path.abspath(__file__))
        wallpaper_dir = os.path.join(base_path, "themes", "img")
        selected_wallpaper = None
        
        if os.path.exists(wallpaper_dir):
            images = [f for f in os.listdir(wallpaper_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if images:
                selected_wallpaper = os.path.join(wallpaper_dir, random.choice(images))
        
        if not selected_wallpaper:
            default_bg = os.path.join(base_path, "themes", "img", "wizard_bg.jpeg")
            if os.path.exists(default_bg):
                selected_wallpaper = default_bg

        if selected_wallpaper:
            self.bg_label = QLabel(self)
            self.bg_label.setGeometry(0, 0, 1200, 900)
            self.bg_label.setPixmap(QPixmap(selected_wallpaper))
            self.bg_label.setScaledContents(True)
            self.bg_label.setStyleSheet("opacity: 0.2;") 
            self.bg_label.lower()
        
        self.project_db_path = None
        self.engagement_type = "Pentest"
        self.base_width = 1200

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget(self)
        self.layout.addWidget(self.container)

        self.page_welcome = QFrame(self.container)
        self.page_welcome.setGeometry(0, 0, self.base_width, 900)
        self.setup_welcome_ui()

        self.page_selection = QFrame(self.container)
        self.page_selection.setGeometry(self.base_width, 0, self.base_width, 900)
        self.setup_selection_ui()

        self.page_create = QFrame(self.container)
        self.page_create.setGeometry(self.base_width, 0, self.base_width, 900)
        self.setup_create_ui()

        self.page_load = QFrame(self.container)
        self.page_load.setGeometry(self.base_width, 0, self.base_width, 900)
        self.setup_load_ui()

        self.current_page = self.page_welcome
        self.history = [] 

        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: #ffffff; }
            QLabel { color: #e0e0e0; font-family: 'Arial'; }
            QLineEdit, QComboBox, QDateEdit, QListWidget, QTextEdit {
                background-color: #2f2f40; color: #00d2ff;
                border: 2px solid #4a4a5e; border-radius: 8px; padding: 10px;
                font-size: 16px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QListWidget:focus, QTextEdit:focus {
                border: 2px solid #00d2ff;
            }
            QPushButton {
                background-color: #2f2f40; color: white;
                border: 1px solid #4a4a5e; padding: 15px; border-radius: 8px; font-size: 16px;
            }
            QPushButton:hover { background-color: #3e3e50; border-color: #00d2ff; color: #00d2ff; }
            QPushButton#ActionBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d2ff, stop:1 #3a7bd5);
                border: none; border-radius: 30px; font-size: 22px; font-weight: bold; color: white;
            }
            QPushButton#ActionBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a7bd5, stop:1 #00d2ff);
            }
            QPushButton#BackBtn { background-color: transparent; border: none; color: #8888aa; font-size: 18px; font-weight: bold; }
            QPushButton#BackBtn:hover { color: #00d2ff; }
            QPushButton#ProjectBtn { font-size: 20px; font-weight: bold; padding: 30px; border: 2px solid #4a4a5e; }
            QPushButton#ProjectBtn:hover { border: 2px solid #00d2ff; background-color: #252535; }
            QFrame { background-color: transparent; border: none; }
            QDialog { background-color: #1e1e2f; color: #ffffff; }
        """)

    def setup_welcome_ui(self):
        layout = QVBoxLayout(self.page_welcome)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        
        title = QLabel("RECON AUTOMATOR")
        title.setFont(QFont("Arial", 48, QFont.Bold))
        title.setStyleSheet("color: #00d2ff;") 
        
        subtitle = QLabel("Your cozy companion for security engagements.")
        subtitle.setFont(QFont("Arial", 18))
        subtitle.setStyleSheet("color: #a0a0b0; margin-bottom: 40px;")

        btn_start = QPushButton("START JOURNEY ➔")
        btn_start.setObjectName("ActionBtn")
        btn_start.setFixedSize(300, 60)
        btn_start.setCursor(Qt.PointingHandCursor)
        btn_start.clicked.connect(lambda: self.slide_to_page(self.page_selection))

        layout.addStretch()
        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignCenter)
        layout.addWidget(btn_start, alignment=Qt.AlignCenter)
        layout.addStretch()

    def start_new_project(self):
        self.reset_create_state()
        self.slide_to_page(self.page_create)

    def setup_selection_ui(self):
        layout = QVBoxLayout(self.page_selection)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(40, 40, 40, 0)
        btn_back = QPushButton("← Back")
        btn_back.setObjectName("BackBtn")
        btn_back.setFixedWidth(100)
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.clicked.connect(self.slide_back)
        top_bar.addWidget(btn_back)
        top_bar.addStretch() 
        layout.addLayout(top_bar)
        
        layout.addStretch()
        lbl_select = QLabel("Initialize Engagement")
        lbl_select.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_select.setStyleSheet("margin-bottom: 30px; color: #ffffff;")
        layout.addWidget(lbl_select, alignment=Qt.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(40)
        btn_layout.setAlignment(Qt.AlignCenter)

        btn_new = QPushButton("Create New Project")
        btn_new.setObjectName("ProjectBtn")
        btn_new.setFixedSize(300, 200)
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.start_new_project)

        btn_load = QPushButton("Load Existing Project")
        btn_load.setObjectName("ProjectBtn")
        btn_load.setFixedSize(300, 200)
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.clicked.connect(self.prepare_and_slide_to_load)

        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_load)
        layout.addLayout(btn_layout)
        layout.addStretch()
        layout.addStretch()

    def setup_create_ui(self):
        self.domain_mode = None 
        self.domain_data = ""
        self.scope_mode = None
        self.scope_data = ""

        layout = QVBoxLayout(self.page_create)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(40, 40, 40, 0)
        btn_back = QPushButton("← Back")
        btn_back.setObjectName("BackBtn")
        btn_back.setFixedWidth(100)
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.clicked.connect(self.slide_back)
        top_bar.addWidget(btn_back)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(10)
        form_widget.setFixedWidth(700) 

        lbl_title = QLabel("Project Details & Scope")
        lbl_title.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff; margin-bottom: 10px;")
        
        self.inp_client = QLineEdit()
        self.inp_client.setPlaceholderText("Client Name (e.g. Acme Corp)")
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Pentest", "Bug Bounty"])
        
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate().addDays(14))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        lbl_dom = QLabel("Target Domains:")
        h_dom = QHBoxLayout()
        self.inp_domains_display = QLineEdit()
        self.inp_domains_display.setPlaceholderText("Select file or Create...")
        self.inp_domains_display.setReadOnly(True)
        btn_dom_browse = QPushButton("Browse")
        btn_dom_browse.setFixedWidth(100)
        btn_dom_browse.clicked.connect(self.browse_domains)
        btn_dom_create = QPushButton("Edit/Create")
        btn_dom_create.setFixedWidth(140)
        btn_dom_create.clicked.connect(self.create_domains)
        h_dom.addWidget(self.inp_domains_display)
        h_dom.addWidget(btn_dom_browse)
        h_dom.addWidget(btn_dom_create)

        lbl_scope = QLabel("Scope / IP Ranges:")
        h_scope = QHBoxLayout()
        self.inp_scope_display = QLineEdit()
        self.inp_scope_display.setPlaceholderText("Select file or Create...")
        self.inp_scope_display.setReadOnly(True)
        btn_scope_browse = QPushButton("Browse")
        btn_scope_browse.setFixedWidth(100)
        btn_scope_browse.clicked.connect(self.browse_scope)
        btn_scope_create = QPushButton("Edit/Create")
        btn_scope_create.setFixedWidth(140)
        btn_scope_create.clicked.connect(self.create_scope)
        h_scope.addWidget(self.inp_scope_display)
        h_scope.addWidget(btn_scope_browse)
        h_scope.addWidget(btn_scope_create)

        btn_create = QPushButton("Create & Launch")
        btn_create.setObjectName("ActionBtn")
        btn_create.setFixedSize(300, 60)
        btn_create.setCursor(Qt.PointingHandCursor)
        btn_create.clicked.connect(self.finalize_create_project)

        form_layout.addWidget(lbl_title, alignment=Qt.AlignCenter)
        form_layout.addWidget(QLabel("Client Name:"))
        form_layout.addWidget(self.inp_client)
        form_layout.addWidget(QLabel("Engagement Type:"))
        form_layout.addWidget(self.combo_type)
        form_layout.addWidget(QLabel("Deadline:"))
        form_layout.addWidget(self.date_edit)
        form_layout.addWidget(lbl_dom)
        form_layout.addLayout(h_dom)
        form_layout.addWidget(lbl_scope)
        form_layout.addLayout(h_scope)
        form_layout.addSpacing(20)
        form_layout.addWidget(btn_create, alignment=Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(form_widget, alignment=Qt.AlignCenter)
        layout.addStretch()
    
    def reset_create_state(self):
        self.domain_mode = None
        self.domain_data = ""
        self.scope_mode = None
        self.scope_data = ""
        self.inp_domains_display.clear()
        self.inp_scope_display.clear()

    def setup_load_ui(self):
        layout = QVBoxLayout(self.page_load)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(40, 40, 40, 0)
        btn_back = QPushButton("← Back")
        btn_back.setObjectName("BackBtn")
        btn_back.setFixedWidth(100)
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.clicked.connect(self.slide_back)
        top_bar.addWidget(btn_back)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(150, 0, 150, 0)
        content_layout.setSpacing(20)

        lbl_title = QLabel("Select Project")
        lbl_title.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff;")
        
        lbl_path = QLabel(f"Scanning: {os.getcwd()}")
        lbl_path.setStyleSheet("color: #8888aa; font-style: italic;")

        self.db_list_widget = QListWidget()
        self.db_list_widget.setCursor(Qt.PointingHandCursor)
        self.db_list_widget.itemDoubleClicked.connect(self.finalize_load_project)

        btn_browse = QPushButton("📂 Navigate Filesystem...")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet("""
            QPushButton { background-color: #2f2f40; border: 2px dashed #4a4a5e; color: #888; }
            QPushButton:hover { border: 2px dashed #00d2ff; color: #00d2ff; }
        """)
        btn_browse.clicked.connect(self.browse_for_db)

        content_layout.addWidget(lbl_title, alignment=Qt.AlignCenter)
        content_layout.addWidget(lbl_path, alignment=Qt.AlignCenter)
        content_layout.addWidget(self.db_list_widget)
        content_layout.addWidget(btn_browse)

        layout.addStretch()
        layout.addLayout(content_layout)
        layout.addStretch()

    # --- LOGIC & ANIMATIONS ---
    def slide_to_page(self, target_page):
        target_page.move(self.base_width, 0)
        self.history.append(self.current_page)
        self.anim_out = QPropertyAnimation(self.current_page, b"pos")
        self.anim_out.setDuration(400)
        self.anim_out.setStartValue(QPoint(0, 0))
        self.anim_out.setEndValue(QPoint(-self.base_width, 0))
        self.anim_out.setEasingCurve(QEasingCurve.InOutQuart)
        self.anim_in = QPropertyAnimation(target_page, b"pos")
        self.anim_in.setDuration(400)
        self.anim_in.setStartValue(QPoint(self.base_width, 0))
        self.anim_in.setEndValue(QPoint(0, 0))
        self.anim_in.setEasingCurve(QEasingCurve.InOutQuart)
        self.anim_out.start()
        self.anim_in.start()
        self.current_page = target_page

    def slide_back(self):
        if not self.history: return
        prev_page = self.history.pop()
        prev_page.move(-self.base_width, 0)
        self.anim_out = QPropertyAnimation(self.current_page, b"pos")
        self.anim_out.setDuration(400)
        self.anim_out.setStartValue(QPoint(0, 0))
        self.anim_out.setEndValue(QPoint(self.base_width, 0))
        self.anim_out.setEasingCurve(QEasingCurve.InOutQuart)
        self.anim_in = QPropertyAnimation(prev_page, b"pos")
        self.anim_in.setDuration(400)
        self.anim_in.setStartValue(QPoint(-self.base_width, 0))
        self.anim_in.setEndValue(QPoint(0, 0))
        self.anim_in.setEasingCurve(QEasingCurve.InOutQuart)
        self.anim_out.start()
        self.anim_in.start()
        self.current_page = prev_page

    # --- LOAD LOGIC ---
    def prepare_and_slide_to_load(self):
        self.db_list_widget.clear()
        valid_files = glob.glob("project_data.db") + glob.glob("*/project_data.db")
        if not valid_files:
            item = "No project databases found in current folder."
            self.db_list_widget.addItem(item)
            self.db_list_widget.item(0).setFlags(Qt.NoItemFlags)
        else:
            for f in valid_files:
                self.db_list_widget.addItem(f)
        self.slide_to_page(self.page_load)

    def finalize_load_project(self, item):
        filename = item.text()
        if not filename or "No project" in filename: return
        full_path = os.path.abspath(filename)
        if os.path.exists(full_path):
            self.project_db_path = full_path
            data = project_db.load_project_data(full_path)
            if data:
                self.engagement_type = data.get('engagement_type', 'Pentest')
            self.accept()

    def browse_for_db(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Project Database", os.getcwd(), "SQLite Files (*.db *.sqlite3);;All Files (*)"
        )
        if file_path:
            if project_db.is_valid_project_db(file_path):
                self.project_db_path = file_path
                data = project_db.load_project_data(file_path)
                if data:
                    self.engagement_type = data.get('engagement_type', 'Pentest')
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid File", "This file is not a valid Project Database.")

    # --- CREATE LOGIC ---
    def browse_domains(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Domains File", "", "Text Files (*.txt *.md);;All Files (*)")
        if path:
            self.domain_mode = 'file'
            self.domain_data = path
            self.inp_domains_display.setText(os.path.basename(path))

    def create_domains(self):
        curr = self.domain_data if self.domain_mode == 'content' else ""
        dlg = SimpleTextEditorDialog("Edit Domains", curr, self)
        if dlg.exec_():
            self.domain_mode = 'content'
            self.domain_data = dlg.get_text()
            self.inp_domains_display.setText("[Manual Input Set]")

    def browse_scope(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Scope File", "", "Text Files (*.txt *.md);;All Files (*)")
        if path:
            self.scope_mode = 'file'
            self.scope_data = path
            self.inp_scope_display.setText(os.path.basename(path))

    def create_scope(self):
        curr = self.scope_data if self.scope_mode == 'content' else ""
        dlg = SimpleTextEditorDialog("Edit Scope", curr, self)
        if dlg.exec_():
            self.scope_mode = 'content'
            self.scope_data = dlg.get_text()
            self.inp_scope_display.setText("[Manual Input Set]")

    def finalize_create_project(self):
        client = self.inp_client.text().strip()
        eng_type = self.combo_type.currentText()
        deadline = self.date_edit.date().toString("yyyy-MM-dd")
        
        if not client:
            QMessageBox.warning(self, "Missing Info", "Client Name is required.")
            return

        root_path = os.getcwd()
        folder_name = f"{client.replace(' ', '_')}_Engagement"
        full_project_path = os.path.join(root_path, folder_name)
        
        if not os.path.exists(full_project_path):
            try:
                os.makedirs(full_project_path)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {e}")
                return

        final_domains_path = os.path.join(full_project_path, "domains.txt")
        try:
            if self.domain_mode == 'content':
                with open(final_domains_path, 'w', encoding='utf-8') as f:
                    f.write(self.domain_data)
            elif self.domain_mode == 'file' and os.path.exists(self.domain_data):
                shutil.copy(self.domain_data, final_domains_path)
            else:
                open(final_domains_path, 'w').close() 
        except Exception as e:
            print(f"Error saving domains: {e}")

        final_scope_path = os.path.join(full_project_path, "scope.txt")
        try:
            if self.scope_mode == 'content':
                with open(final_scope_path, 'w', encoding='utf-8') as f:
                    f.write(self.scope_data)
            elif self.scope_mode == 'file' and os.path.exists(self.scope_data):
                shutil.copy(self.scope_data, final_scope_path)
            else:
                open(final_scope_path, 'w').close()
        except Exception as e:
            print(f"Error saving scope: {e}")

        self.project_db_path = project_db.initialize_project_db(full_project_path)
        
        domain_list = []
        if os.path.exists(final_domains_path):
            with open(final_domains_path, 'r') as f:
                domain_list = [l.strip() for l in f if l.strip()]

        project_db.save_project_details(self.project_db_path, client, eng_type, deadline, domain_list)
        self.engagement_type = eng_type
        self.accept()

# ---------------------------------------------------------
# 2. MAIN APPLICATION 
# ---------------------------------------------------------
class CyberSecBuddyApp(QMainWindow):
    def __init__(self, engagement_type="Pentest", project_db_path=None):
        super().__init__()
        self.restart_requested = False
        
        from modules.scan_control import ScanControlWidget
        from modules.playground import PlaygroundTabWidget
        from modules.custom_commands import CustomCommandsWidget
        from modules.sudo_terminal import SudoTerminalWidget
        from modules.report_tab import ReportTabWidget
        from modules.attack_vectors import AttackVectorsWidget
        from modules.enumeration import EnumerationWidget
        from modules.c2 import C2Widget

        self.engagement_type = engagement_type
        self.project_db_path = project_db_path
        
        # Guard clause for new projects to ensure path handling
        attack_db_path = None
        client_name = "Target"
        
        if self.project_db_path:
            self.project_data = project_db.load_project_data(self.project_db_path)
            client_name = self.project_data.get('client_name', 'Unknown')
            self.setWindowTitle(f"Cybersecurity Buddy - {client_name} [{self.engagement_type}]")
            self.working_directory = os.path.dirname(self.project_db_path)
        else:
            self.setWindowTitle(f"Cybersecurity Buddy - [{self.engagement_type}]")
            self.working_directory = os.path.expanduser("~")
            
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.base_path, "resources", "img")

        app_icon_path = os.path.join(self.icon_path, "app.png")
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        # Modules
        self.scan_control_tab = ScanControlWidget(self.working_directory, self.icon_path, project_db_path=self.project_db_path)
        self.terminal_tab = CustomCommandsWidget(self.working_directory, self.icon_path)
        self.sudo_terminal_tab = SudoTerminalWidget(self.icon_path)
        self.report_tab = ReportTabWidget(db_path=self.project_db_path, project_name=client_name)
        self.playground_tab = PlaygroundTabWidget(self.working_directory, self.icon_path, self.terminal_tab)
        
        project_folder = os.path.dirname(self.project_db_path) if self.project_db_path else self.working_directory
        self.attack_vectors_widget = AttackVectorsWidget(project_folder=project_folder, attack_db_path=attack_db_path)
        # UPDATED: Pass project_db_path to EnumerationWidget
        self.enumeration_tab = EnumerationWidget(self.working_directory, project_db_path=self.project_db_path)
        self.c2_tab = C2Widget(self.working_directory)

        self.enumeration_widget = QLabel("Enumeration Tools")
        self.enumeration_widget.setAlignment(Qt.AlignCenter)
        self.exploiting_widget = QLabel("Exploitation Framework")
        self.exploiting_widget.setAlignment(Qt.AlignCenter)

        if self.engagement_type == "Pentest":
            self.setup_pentest_ui()
        else:
            self.setup_bug_bounty_ui()

        self.setup_global_menus()

        # Connect Signals
        self.scan_control_tab.scan_updated.connect(self.playground_tab.refresh_playground)
        self.scan_control_tab.cwd_changed.connect(self.on_cwd_changed)
        self.scan_control_tab.theme_changed.connect(self.apply_theme)
        self.scan_control_tab.active_task_count_changed.connect(self.update_task_menu_text)
        
        self.apply_theme()

    # ... rest of the class is unchanged ...
    def setup_global_menus(self):
        menubar = self.menuBar()
        
        session_menu = menubar.addMenu("Session")
        action_restart = QAction("Switch Project...", self)
        action_restart.triggered.connect(self.restart_to_wizard)
        session_menu.addAction(action_restart)
        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self.close)
        session_menu.addAction(action_exit)

        tools_menu = menubar.addMenu("Tools")
               
        tools_menu.addSeparator()

        action_settings = QAction("Project Settings", self)
        action_settings.triggered.connect(self.open_project_settings)
        tools_menu.addAction(action_settings)

        action_commands = QAction("Manage Commands...", self)
        action_commands.triggered.connect(self.scan_control_tab.open_command_editor)
        tools_menu.addAction(action_commands)

        tools_menu.addSeparator()

        self.action_bg_tasks = QAction("View Background Tasks (0)", self)
        self.action_bg_tasks.triggered.connect(self.scan_control_tab.show_background_tasks)
        tools_menu.addAction(self.action_bg_tasks)

        term_menu = menubar.addMenu("Terminals")
        action_user_term = QAction("User Terminal", self)
        action_user_term.triggered.connect(self.open_user_terminal_dialog)
        term_menu.addAction(action_user_term)
        action_sudo_term = QAction("Root Terminal", self)
        action_sudo_term.triggered.connect(self.open_sudo_terminal_dialog)
        term_menu.addAction(action_sudo_term)

        view_menu = menubar.addMenu("View")
        theme_menu = view_menu.addMenu("Theme")
        action_dark = QAction("Dark Mode", self)
        action_dark.triggered.connect(lambda: self.change_theme_setting("dark"))
        theme_menu.addAction(action_dark)
        action_light = QAction("Light Mode", self)
        action_light.triggered.connect(lambda: self.change_theme_setting("light"))
        theme_menu.addAction(action_light)

    def open_project_settings(self):
        """Opens the ProjectEditDialog and updates UI on save."""
        if not self.project_db_path:
            QMessageBox.warning(self, "No Project", "No active project loaded.")
            return

        dlg = project_db.ProjectEditDialog(self, self.project_db_path)
        if dlg.exec_() == QDialog.Accepted:
            # Refresh Title
            data = project_db.load_project_data(self.project_db_path)
            if data:
                client = data.get('client_name', 'Unknown')
                self.setWindowTitle(f"Cybersecurity Buddy - {client} [{self.engagement_type}]")
            
            # Refresh Scan Control Info Labels if they exist
            if hasattr(self.scan_control_tab, 'load_project_info'):
                self.scan_control_tab.load_project_info()
                self.scan_control_tab.lbl_target.setText(f"TARGET: {client}")

    def update_task_menu_text(self, count):
        if hasattr(self, 'action_bg_tasks'):
            self.action_bg_tasks.setText(f"View Background Tasks ({count})")

    def setup_bug_bounty_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self.scan_control_tab, "Scan Control")
        self.tabs.addTab(self.playground_tab, "Playground")
        self.tabs.addTab(self.terminal_tab, "Terminal")
        self.tabs.addTab(self.sudo_terminal_tab, "Sudo Terminal")
        self.tabs.addTab(self.report_tab, "Reporting")
        self.tabs.addTab(self.c2_tab, "C2 & Listeners")

    def setup_pentest_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("PentestSidebar")
        self.sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.scan_control_tab) 
        self.content_stack.addWidget(self.enumeration_tab)
        self.content_stack.addWidget(self.playground_tab)
        self.content_stack.addWidget(self.attack_vectors_widget)
        self.content_stack.addWidget(self.exploiting_widget)
        self.content_stack.addWidget(self.report_tab)
        self.content_stack.addWidget(self.c2_tab)

        self.sidebar_btns = []
        labels = ["Scan Control", "Enumeration", "Playground", "Threat Modeling", "Exploiting", " Reporting", "C2 / Listeners"]
        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_pentest_tab(idx))
            self.sidebar_btns.append(btn)
            sidebar_layout.addWidget(btn)
        
        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content_stack)
        self.sidebar_btns[0].click()

    def switch_pentest_tab(self, index):
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.sidebar_btns):
            btn.setChecked(i == index)

    def restart_to_wizard(self):
        self.restart_requested = True
        self.close()

    def change_theme_setting(self, mode):
        command_db.set_setting('active_theme', mode)
        self.apply_theme()

    def apply_theme(self):
        theme_mode = command_db.get_setting('active_theme') or "dark"
        eng_mode = "pentest" if self.engagement_type == "Pentest" else "bug_bounty"
        
        qss_filename = f"{eng_mode}_{theme_mode}.qss"
        qss_path = os.path.join(self.base_path, "themes", qss_filename)

        if os.path.exists(qss_path):
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        
        if hasattr(self, 'scan_control_tab'):
            self.scan_control_tab.apply_theme(theme_mode)
        if hasattr(self, 'playground_tab'):
            self.playground_tab.apply_theme()

    def open_user_terminal_dialog(self):
        self.term_window = QDialog(self)
        self.term_window.setWindowTitle("User Terminal")
        self.term_window.resize(800, 600)
        layout = QVBoxLayout(self.term_window)
        layout.addWidget(self.terminal_tab)
        self.term_window.show()

    def open_sudo_terminal_dialog(self):
        self.sudo_window = QDialog(self)
        self.sudo_window.setWindowTitle("Root Terminal (Sudo)")
        self.sudo_window.resize(800, 600)
        layout = QVBoxLayout(self.sudo_window)
        layout.addWidget(self.sudo_terminal_tab)
        self.sudo_window.show()

    def on_cwd_changed(self, new_path):
        self.working_directory = new_path
        self.playground_tab.set_working_directory(new_path)
        self.terminal_tab.set_working_directory(new_path)
        command_db.set_setting('last_cwd', new_path)

        if hasattr(self, 'attack_vectors_widget'):
            self.attack_vectors_widget.db_manager.project_folder = new_path
            self.attack_vectors_widget.db_manager.network_db_path = os.path.join(new_path, "network_information.db")
            self.attack_vectors_widget.refresh_view()

        if hasattr(self.scan_control_tab, 'on_cwd_changed'):
            self.scan_control_tab.on_cwd_changed(new_path)

    def closeEvent(self, event):
        if hasattr(self, 'terminal_tab'):
            self.terminal_tab.stop_all_processes()
        if hasattr(self, 'scan_control_tab') and self.scan_control_tab.worker and self.scan_control_tab.worker.isRunning():
            self.scan_control_tab.worker.stop()
        event.accept()

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    
    app = QApplication(sys.argv)

    command_db.initialize_db()

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "img", "app.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    while True:
        wizard = StartupWizard()
        if wizard.exec_() != QDialog.Accepted:
            break
        
        main_win = CyberSecBuddyApp(
            engagement_type=wizard.engagement_type,
            project_db_path=wizard.project_db_path
        )
        main_win.showMaximized() 
        
        app.exec_()
        
        if not main_win.restart_requested:
            break