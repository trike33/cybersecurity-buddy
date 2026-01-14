import sys
import random
import os
import glob
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QDialog, 
                             QVBoxLayout, QLabel, QPushButton, QWidget, 
                             QHBoxLayout, QStackedWidget, QFrame, QAction,
                             QFileDialog, QMessageBox, QListWidget, QLineEdit,
                             QComboBox, QDateEdit, QTextEdit, QDialogButtonBox, QMenu)
from PyQt5.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QPoint, QDate, QTimer
from PyQt5.QtGui import QIcon, QFont, QColor, QPixmap, QMovie, QCursor
import shutil
import socket

# ---------------------------------------------------------
# SETUP & UTILS
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Only import lightweight utils here
from utils.launcher_hub import AppLauncher
from utils import db as command_db
from utils import project_db

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------
# THE MODULE CONTAINER (The "Window Placeholder")
# ---------------------------------------------------------
class ModuleContainerWindow(QMainWindow):
    """
    This is a standalone window wrapper for a single module tab.
    It gives the tab a proper window frame, menus, and styling.
    """
    def __init__(self, module_widget, title, project_name, engagement_type, theme="dark"):
        super().__init__()
        self.setWindowTitle(f"{title} - {project_name} [{engagement_type}]")
        self.resize(1100, 750)
        
        # 1. Set the central widget to the specific tool (Scan, Exploit, etc.)
        self.setCentralWidget(module_widget)
        
        # 2. Setup Menus (So it feels like a real app)
        self.setup_menu()
        
        # 3. Apply Theme
        self.apply_theme(theme, engagement_type)
        
        # 4. Set Icon
        icon_path = resource_path(os.path.join("resources", "img", "app.png"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        close_action = QAction("Close Tool", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        view_menu = menubar.addMenu("View")
        # You can add theme toggles here if desired

    def apply_theme(self, theme_mode, engagement_type):
        base_path = resource_path(".")
        eng_mode = "pentest" if engagement_type == "Pentest" else "bug_bounty"
        qss_filename = f"{eng_mode}_{theme_mode}.qss"
        qss_path = os.path.join(base_path, "themes", qss_filename)
        if os.path.exists(qss_path):
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
# ---------------------------------------------------------
# UI COMPONENT: BEAUTIFUL BUDDY ALERT
# ---------------------------------------------------------
class BuddyAlert(QDialog):
    """
    A custom, frameless, beautiful dialog for health checks.
    """
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(450, 280)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Container Frame (for the border and background)
        self.container = QFrame(self)
        self.container.setObjectName("BuddyFrame")
        self.container.setStyleSheet("""
            QFrame#BuddyFrame {
                background-color: #1e1e2f;
                border: 2px solid #00d2ff;
                border-radius: 16px;
            }
            QLabel { color: #ffffff; font-family: 'Segoe UI', Arial; }
        """)
        
        # Drop Shadow Effect
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 210, 255, 100)) # Neon blue glow
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)
        container_layout.setContentsMargins(20, 25, 20, 25)

        # Title / Header
        lbl_title = QLabel("👾 CYBERSEC BUDDY")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #00d2ff; font-size: 14px; font-weight: bold; letter-spacing: 2px;")
        
        # Main Message
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setStyleSheet("font-size: 18px; line-height: 1.4; color: #e0e0e0;")

        # Action Button
        btn_ok = QPushButton("Roger that! 🚀")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedSize(160, 45)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d2ff, stop:1 #3a7bd5);
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 22px;
                border: none;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a7bd5, stop:1 #00d2ff);
            }
        """)
        btn_ok.clicked.connect(self.accept)

        # Add widgets to layout
        container_layout.addWidget(lbl_title)
        container_layout.addWidget(lbl_msg)
        container_layout.addStretch()
        container_layout.addWidget(btn_ok, alignment=Qt.AlignCenter)

        layout.addWidget(self.container)
    
    # Optional: Allow dragging the frameless window
    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

# ---------------------------------------------------------
# LAZY MODULE LOADER FACTORY
# ---------------------------------------------------------
class ModuleManager:
    """
    Handles the lazy loading of modules and acts as the 
    Context-Aware CyberSec Buddy.
    """
    def __init__(self, project_db_path, engagement_type):
        self.project_db_path = project_db_path
        self.engagement_type = engagement_type
        
        # Load basic project data
        self.project_data = {}
        if self.project_db_path:
            self.project_data = project_db.load_project_data(self.project_db_path)
            
        self.client_name = self.project_data.get('client_name', 'Unknown')
        self.working_directory = os.path.dirname(self.project_db_path) if self.project_db_path else os.path.expanduser("~")
        
        # Helper for icons
        self.icon_path = resource_path(os.path.join("resources", "img"))
        
        # Keep track of open windows so they don't get garbage collected
        self.open_windows = []

        # --- START BUDDY TIMER ---
        self.recent_alerts = []
        self.setup_health_monitor()

    def setup_health_monitor(self):
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.trigger_buddy_alert)
        # 2 hours = 7200000 ms. (Set to 10000 ms to test it quickly!)
        self.check_interval = 1800000 
        self.health_timer.start(self.check_interval)

    def trigger_buddy_alert(self):
        """
        Triggers a context-aware alert.
        Ensures the last 2 messages are not repeated.
        """
        # A rich list of messages with HTML formatting for the UI
        all_messages = [
            # Hydration
            "💧 <b>Hydration Check:</b><br>You've been scanning for ages.<br>Hydrate or diedrate!",
            "🚰 <b>Water Break:</b><br>Your brain is 73% water.<br>Refill the tank to keep the shells popping.",
            
            # Coffee
            "☕ <b>Caffeine Critical:</b><br>Packet loss detected in user energy levels.<br>Go grab a fresh coffee.",
            "🍵 <b>Bean Juice Time:</b><br>Step away from the screen.<br>Brew something warm.<br>Smell the beans.",

            # Social / Colleagues
            "🗣️ <b>Human Protocol:</b><br>Go bother a colleague.<br>Social engineering requires... socializing.<br>Say hello to someone!",
            "🤝 <b>Touch Grass (Or Carpet):</b><br>Walk over to a teammate.<br>Ask them about their day.<br>Don't mention the pentest.",

            # Physical / Eyes
            "👀 <b>Vision Saving:</b><br>Look at something 20 feet away<br>for 20 seconds.<br>Do it right now.",
            "🧘 <b>Posture Check:</b><br>Unclench your jaw.<br>Drop your shoulders.<br>Fix the shrimp posture.",
            "🧠 <b>Brain Fog Alert:</b><br>Deep breath.<br>You're doing great work,<br>but your brain needs oxygen."
        ]
        
        # Filter out messages that were shown recently
        available_messages = [m for m in all_messages if m not in self.recent_alerts]
        
        # Fallback if we somehow exhausted the list (unlikely with this logic, but safe coding)
        if not available_messages:
            available_messages = all_messages
            self.recent_alerts = []

        # Select a random message
        encouragement = random.choice(available_messages)
        
        # Update History (Keep only the last 2)
        self.recent_alerts.append(encouragement)
        if len(self.recent_alerts) > 2:
            self.recent_alerts.pop(0)

        # Launch the Beautiful Alert
        alert = BuddyAlert(encouragement)
        alert.exec_()

    def launch_module(self, module_id):
        widget = None
        title = "Tool"

        # LAZY IMPORTS: We only import inside the `if` block
        try:
            if module_id == "settings":
                dlg = project_db.ProjectEditDialog(None, self.project_db_path)
                if dlg.exec_() == QDialog.Accepted:
                    self.project_data = project_db.load_project_data(self.project_db_path)
                    self.client_name = self.project_data.get('client_name', 'Unknown')
                return 

            elif module_id == "scan":
                from modules.scan_control import ScanControlWidget
                widget = ScanControlWidget(self.working_directory, self.icon_path, project_db_path=self.project_db_path)
                title = "Scan Control"

            elif module_id == "enum":
                from modules.enumeration import EnumerationWidget
                widget = EnumerationWidget(self.working_directory, project_db_path=self.project_db_path)
                title = "Enumeration"

            elif module_id == "threat":
                from modules.attack_vectors import AttackVectorsWidget
                widget = AttackVectorsWidget(project_folder=self.working_directory, attack_db_path=None)
                title = "Threat Modeling"

            elif module_id == "exploit":
                from modules.exploiting import ExploitingWidget
                widget = ExploitingWidget(project_path=self.working_directory)
                title = "Exploitation Framework"
            
            elif module_id == "brute":
                from modules.bruteforce import BruteForceWidget
                widget = BruteForceWidget(self.working_directory)
                title = "Brute Force Manager"

            elif module_id == "c2":
                from modules.c2 import C2Widget
                widget = C2Widget(self.working_directory)
                title = "C2 & Listeners"

            elif module_id == "report":
                from modules.report_tab import ReportTabWidget
                widget = ReportTabWidget(db_path=self.project_db_path, project_name=self.client_name)
                title = "Reporting"

            elif module_id == "dashboard":
                from modules.dashboard import DashboardWidget
                whitelisted = ["stegosaurus", "ankylo"]
                is_home = socket.gethostname() in whitelisted
                widget = DashboardWidget(self.project_db_path, hostname_test=is_home)
                title = "Dashboard"

            elif module_id == "postexp":
                from modules.post_exploitation import PostExploitationWidget
                widget = PostExploitationWidget()
                title = "Post Exploitation"

            elif module_id == "ad":
                from modules.active_directory import ActiveDirectoryWidget
                widget = ActiveDirectoryWidget()
                title = "Active Directory"

            elif module_id == "payload":
                from modules.payload_gen import PayloadGenWidget
                widget = PayloadGenWidget(project_folder=self.working_directory)
                title = "Payload Generator"

            elif module_id == "cve":
                from modules.cve_search import CVESearchWidget
                widget = CVESearchWidget()
                title = "CVE Search"

            elif module_id == "privesc":
                from modules.privesc_map import PrivEscWidget
                widget = PrivEscWidget()
                title = "Privilege Escalation"

            elif module_id == "play":
                from modules.playground import PlaygroundTabWidget
                from modules.custom_commands import CustomCommandsWidget
                term = CustomCommandsWidget(self.working_directory, self.icon_path)
                widget = PlaygroundTabWidget(self.working_directory, self.icon_path, term, hostname_test=False)
                title = "Playground"

            else:
                # Use the new alert style for errors/info too if you want!
                # BuddyAlert(f"Module '{module_id}' is not yet linked.").exec_()
                QMessageBox.information(None, "Coming Soon", f"Module '{module_id}' is not yet linked.")
                return

            if widget:
                window = ModuleContainerWindow(
                    module_widget=widget,
                    title=title,
                    project_name=self.client_name,
                    engagement_type=self.engagement_type
                )
                window.showMaximized()
                self.open_windows.append(window)
                window.destroyed.connect(lambda: self.open_windows.remove(window) if window in self.open_windows else None)

        except Exception as e:
            QMessageBox.critical(None, "Load Error", f"Failed to load module '{module_id}':\n{str(e)}")
            import traceback
            traceback.print_exc()

# ---------------------------------------------------------
# PATH HELPER (Fixed Bug)
# ---------------------------------------------------------
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------
# HELPER CLASSES
# ---------------------------------------------------------
class ComingSoonWidget(QWidget):
    """A placeholder widget for tabs currently under development."""
    def __init__(self, title, subtitle="Coming Soon"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        lbl_icon = QLabel("🚧")
        lbl_icon.setFont(QFont("Arial", 60))
        lbl_icon.setStyleSheet("color: #555;")
        
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff;")
        
        lbl_desc = QLabel(subtitle)
        lbl_desc.setFont(QFont("Arial", 16))
        lbl_desc.setStyleSheet("color: #888; font-style: italic;")
        
        layout.addWidget(lbl_icon, alignment=Qt.AlignCenter)
        layout.addWidget(lbl_title, alignment=Qt.AlignCenter)
        layout.addWidget(lbl_desc, alignment=Qt.AlignCenter)

class SimpleTextEditorDialog(QDialog):
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

        # --- BACKGROUND LOGIC (Fixed Paths) ---
        base_path = resource_path(".")
        wallpaper_dir = os.path.join(base_path, "themes", "img")
        
        # Check for whitelisted hostname for Pokemon wallpapers
        whitelisted_hostnames = ['stegosaurus', 'ankylo']
        if socket.gethostname() in whitelisted_hostnames:
             # Try specific pokemon folder if it exists
             poke_path = os.path.join(wallpaper_dir, "pokemon")
             if os.path.exists(poke_path):
                 wallpaper_dir = poke_path

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
            QLineEdit:focus { border: 2px solid #00d2ff; }
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
    def __init__(self, engagement_type="Pentest", project_db_path=None, initial_module="dashboard"):
        super().__init__()
        self.restart_requested = False
        
        # --- FIXED IMPORTS ---
        from modules.scan_control import ScanControlWidget
        from modules.playground import PlaygroundTabWidget
        from modules.custom_commands import CustomCommandsWidget
        from modules.sudo_terminal import SudoTerminalWidget
        from modules.report_tab import ReportTabWidget
        from modules.attack_vectors import AttackVectorsWidget
        from modules.enumeration import EnumerationWidget
        from modules.c2 import C2Widget
        from modules.dashboard import DashboardWidget
        from modules.bruteforce import BruteForceWidget
        # Corrected class name
        from modules.exploiting import ExploitingWidget  
        # Missing Modules Added
        from modules.cve_search import CVESearchWidget
        from modules.payload_gen import PayloadGenWidget
        from modules.privesc_map import PrivEscWidget
        from modules.post_exploitation import PostExploitationWidget
        from modules.active_directory import ActiveDirectoryWidget

        self.engagement_type = engagement_type
        self.project_db_path = project_db_path
        
        attack_db_path = None
        client_name = "Target"
        
        # Hostname Check for Themes
        whitelisted_hostnames = ["stegosaurus", "ankylo", "kali"]
        self.hostname_test = socket.gethostname() in whitelisted_hostnames
        
        if self.project_db_path:
            self.project_data = project_db.load_project_data(self.project_db_path)
            client_name = self.project_data.get('client_name', 'Unknown')
            self.setWindowTitle(f"Cybersecurity Buddy - {client_name} [{self.engagement_type}]")
            self.working_directory = os.path.dirname(self.project_db_path)
        else:
            self.setWindowTitle(f"Cybersecurity Buddy - [{self.engagement_type}]")
            self.working_directory = os.path.expanduser("~")
            
        # --- FIXED PATHING ---
        self.base_path = resource_path(".")
        self.icon_path = os.path.join(self.base_path, "resources", "img")

        app_icon_path = os.path.join(self.icon_path, "app.png")
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        # --- MODULE INSTANTIATION ---
        self.scan_control_tab = ScanControlWidget(self.working_directory, self.icon_path, project_db_path=self.project_db_path)
        self.terminal_tab = CustomCommandsWidget(self.working_directory, self.icon_path)
        self.sudo_terminal_tab = SudoTerminalWidget(self.icon_path)
        self.report_tab = ReportTabWidget(db_path=self.project_db_path, project_name=client_name)
        self.playground_tab = PlaygroundTabWidget(self.working_directory, self.icon_path, self.terminal_tab, hostname_test=self.hostname_test)
        
        project_folder = os.path.dirname(self.project_db_path) if self.project_db_path else self.working_directory
        
        self.attack_vectors_widget = AttackVectorsWidget(project_folder=project_folder, attack_db_path=attack_db_path)
        self.enumeration_tab = EnumerationWidget(self.working_directory, project_db_path=self.project_db_path)
        self.c2_tab = C2Widget(self.working_directory)
        self.dashboard_tab = DashboardWidget(self.project_db_path, hostname_test=self.hostname_test)
        self.bruteforce_widget = BruteForceWidget(self.working_directory)
        
        # New/Fixed Modules
        self.exploiting_widget = ExploitingWidget(project_path=project_folder)
        self.cve_tab = CVESearchWidget()
        self.payload_tab = PayloadGenWidget(project_folder=project_folder)
        self.privesc_tab = PrivEscWidget()
        self.post_exp_tab = PostExploitationWidget()
        self.ad_tab = ActiveDirectoryWidget()
        self.mitm_tab = ComingSoonWidget("Relaying & MITM", "Tools for ARP spoofing, SMB relaying, and traffic interception.")

        if self.engagement_type == "Pentest":
            self.setup_pentest_ui(initial_module)
        else:
            self.setup_bug_bounty_ui()

        self.setup_global_menus()

        # Connect Signals
        self.scan_control_tab.scan_updated.connect(self.playground_tab.refresh_playground)
        self.scan_control_tab.cwd_changed.connect(self.on_cwd_changed)
        self.scan_control_tab.theme_changed.connect(self.apply_theme)
        self.scan_control_tab.active_task_count_changed.connect(self.update_task_menu_text)
        
        self.apply_theme()

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
        if not self.project_db_path:
            QMessageBox.warning(self, "No Project", "No active project loaded.")
            return

        dlg = project_db.ProjectEditDialog(self, self.project_db_path)
        if dlg.exec_() == QDialog.Accepted:
            data = project_db.load_project_data(self.project_db_path)
            if data:
                client = data.get('client_name', 'Unknown')
                self.setWindowTitle(f"Cybersecurity Buddy - {client} [{self.engagement_type}]")
            
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

    def setup_pentest_ui(self, initial_module):
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
        
        # --- FIXED STACK ORDER (Matches Main.py) ---
        self.content_stack.addWidget(self.scan_control_tab)    # 0
        self.content_stack.addWidget(self.attack_vectors_widget) # 1
        self.content_stack.addWidget(self.enumeration_tab)     # 2
        self.content_stack.addWidget(self.playground_tab)      # 3
        self.content_stack.addWidget(self.exploiting_widget)   # 4
        self.content_stack.addWidget(self.bruteforce_widget)   # 5
        self.content_stack.addWidget(self.c2_tab)              # 6
        self.content_stack.addWidget(self.privesc_tab)         # 7
        self.content_stack.addWidget(self.post_exp_tab)        # 8
        self.content_stack.addWidget(self.ad_tab)              # 9
        self.content_stack.addWidget(self.mitm_tab)            # 10
        self.content_stack.addWidget(self.cve_tab)             # 11
        self.content_stack.addWidget(self.payload_tab)         # 12
        self.content_stack.addWidget(self.report_tab)          # 13
        self.content_stack.addWidget(self.dashboard_tab)       # 14

        self.sidebar_btns = []
        labels = [
            "📡 Scan Control", 
            "🛡️ Threat Modeling", 
            "🔍 Enumeration", 
            "🎡 Playground", 
            "💥 Exploiting", 
            "🔓 Bruteforce", 
            "🎧 C2 / Listeners",
            "🧗 Privilege Escalation",
            "🏴‍☠️ Post Exploitation",
            "🏰 Active Directory",
            "🔁 Relaying / MITM",
            "📋 CVE Search",
            "📦 Payload Gen",
            "📝 Reporting", 
            "📊 Dashboard"
        ]
        
        for i, label in enumerate(labels):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_pentest_tab(idx))
            self.sidebar_btns.append(btn)
            sidebar_layout.addWidget(btn)
        
        sidebar_layout.addStretch()
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content_stack)
        
        # --- Handle Initial Module Jump ---
        # Map launcher IDs to new Stack Indices
        module_map = {
            "scan": 0, "threat": 1, "enum": 2, "play": 3,
            "exploit": 4, "brute": 5, "c2": 6, "report": 13, "dashboard": 14
        }
        
        target_idx = module_map.get(initial_module, 0)
        
        if 0 <= target_idx < len(self.sidebar_btns):
            self.sidebar_btns[target_idx].click()
        else:
            self.sidebar_btns[0].click()

    def switch_pentest_tab(self, index):
        self.content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.sidebar_btns):
            btn.setChecked(i == index)

        if index == 14: # Dashboard index
            self.dashboard_tab.refresh_view()

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

    icon_path = resource_path(os.path.join("resources", "img", "app.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 1. Run Wizard
    # (Uncomment the real wizard logic when pasting)
    wizard = StartupWizard()
    if wizard.exec_() != QDialog.Accepted:
        sys.exit(0)
    
    # 2. Initialize Module Manager (The Logic Controller)
    manager = ModuleManager(wizard.project_db_path, wizard.engagement_type)
    
    # 3. Launch the Hub (The UI)
    base_asset_path = resource_path(".")
    # Project name extraction
    proj_name = os.path.basename(os.path.dirname(wizard.project_db_path)) if wizard.project_db_path else "New Project"
    
    launcher = AppLauncher(proj_name, base_asset_path)
    
    # 4. Connect Hub Signal to Manager Logic
    # This is the magic link. Launcher emits string -> Manager lazy loads module.
    launcher.launch_module_signal.connect(manager.launch_module)
    
    launcher.showMaximized()
    sys.exit(app.exec_())
