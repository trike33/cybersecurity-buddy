import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QDialog, 
                             QVBoxLayout, QLabel, QPushButton, QWidget, 
                             QHBoxLayout, QStackedWidget, QFrame)
from PyQt5.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QPoint, QRect
from PyQt5.QtGui import QIcon, QFont

# Import utility and module classes
from utils import db as command_db
from modules.scan_control import ScanControlWidget
from modules.playground import PlaygroundTabWidget
from modules.custom_commands import CustomCommandsWidget
from modules.sudo_terminal import SudoTerminalWidget
from modules.report_tab import ReportTabWidget

# ---------------------------------------------------------
# New Class: Startup Wizard (Welcome & Engagement Selection)
# ---------------------------------------------------------
class StartupWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome")
        self.setFixedSize(600, 400)
        # Remove standard window frame for a cleaner "splash" look (optional)
        # self.setWindowFlags(Qt.FramelessWindowHint) 
        
        self.engagement_type = None # To store the user's choice

        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Container for the sliding pages
        self.container = QWidget(self)
        self.layout.addWidget(self.container)

        # Page 1: Welcome Page
        self.page_welcome = QFrame(self.container)
        self.page_welcome.setGeometry(0, 0, 600, 400)
        self.setup_welcome_ui()

        # Page 2: Engagement Selection (Initially off-screen to the right)
        self.page_selection = QFrame(self.container)
        self.page_selection.setGeometry(600, 0, 600, 400) # Start position: x=600
        self.setup_selection_ui()

        # Styling
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #eeeeee; }
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton#ActionBtn {
                background-color: #007acc;
                font-weight: bold;
            }
            QPushButton#ActionBtn:hover { background-color: #0098ff; }
        """)

    def setup_welcome_ui(self):
        layout = QVBoxLayout(self.page_welcome)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("Recon Automator")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        
        subtitle = QLabel("Your cozy companion for security engagements.")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setStyleSheet("color: #aaaaaa; margin-bottom: 20px;")

        btn_start = QPushButton("Start Journey")
        btn_start.setObjectName("ActionBtn")
        btn_start.setFixedWidth(200)
        btn_start.clicked.connect(self.animate_slide_left)

        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignCenter)
        layout.addWidget(btn_start, alignment=Qt.AlignCenter)

    def setup_selection_ui(self):
        layout = QVBoxLayout(self.page_selection)
        layout.setAlignment(Qt.AlignCenter)

        lbl_select = QLabel("Select Engagement Type")
        lbl_select.setFont(QFont("Arial", 18, QFont.Bold))
        lbl_select.setStyleSheet("margin-bottom: 30px;")

        # Buttons
        btn_pentest = QPushButton("Pentest")
        btn_pentest.setFixedWidth(250)
        btn_pentest.clicked.connect(lambda: self.finish_wizard("Pentest"))

        btn_bounty = QPushButton("Bug Bounty")
        btn_bounty.setFixedWidth(250)
        btn_bounty.clicked.connect(lambda: self.finish_wizard("Bug Bounty"))

        btn_previous = QPushButton("Load Previous Engagement")
        btn_previous.setFixedWidth(250)
        btn_previous.clicked.connect(lambda: self.finish_wizard("Load Previous"))

        layout.addWidget(lbl_select, alignment=Qt.AlignCenter)
        layout.addWidget(btn_pentest, alignment=Qt.AlignCenter)
        layout.addWidget(btn_bounty, alignment=Qt.AlignCenter)
        layout.addWidget(btn_previous, alignment=Qt.AlignCenter)

    def animate_slide_left(self):
        # Animation group could be used, but two separate animations work fine here
        self.anim_welcome = QPropertyAnimation(self.page_welcome, b"pos")
        self.anim_welcome.setDuration(500)
        self.anim_welcome.setStartValue(QPoint(0, 0))
        self.anim_welcome.setEndValue(QPoint(-600, 0)) # Slide out left
        self.anim_welcome.setEasingCurve(QEasingCurve.InOutQuart)

        self.anim_selection = QPropertyAnimation(self.page_selection, b"pos")
        self.anim_selection.setDuration(500)
        self.anim_selection.setStartValue(QPoint(600, 0)) # Start from right
        self.anim_selection.setEndValue(QPoint(0, 0))   # Slide in to center
        self.anim_selection.setEasingCurve(QEasingCurve.InOutQuart)

        self.anim_welcome.start()
        self.anim_selection.start()

    def finish_wizard(self, selection):
        self.engagement_type = selection
        self.accept() # Closes the dialog with ResultCode.Accepted

# ---------------------------------------------------------
# Main Application
# ---------------------------------------------------------
class CyberSecBuddyApp(QMainWindow):
    def __init__(self, engagement_type=None):
        super().__init__()

        self.setWindowTitle(f"Cybersecurity Buddy App")
        self.setGeometry(100, 100, 1200, 800)
        
        self.engagement_type = engagement_type 
        
        last_cwd = command_db.get_setting('last_cwd')
        if last_cwd and os.path.exists(last_cwd):
            self.working_directory = last_cwd
        else:
            self.working_directory = os.path.expanduser("~")
        
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.base_path, "resources", "img")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.scan_control_tab = ScanControlWidget(self.working_directory, self.icon_path)
        self.terminal_tab = CustomCommandsWidget(self.working_directory, self.icon_path)
        self.playground_tab = PlaygroundTabWidget(self.working_directory, self.icon_path, self.terminal_tab)
        self.sudo_terminal_tab = SudoTerminalWidget(self.icon_path)
        self.report_tab = ReportTabWidget()

        self.tabs.addTab(self.scan_control_tab, "Scan Control")
        self.tabs.addTab(self.playground_tab, "Playground")
        self.tabs.addTab(self.terminal_tab, "Terminal")
        self.tabs.addTab(self.sudo_terminal_tab, "Sudo Terminal")
        self.tabs.addTab(self.report_tab, "Reporting")

        self.scan_control_tab.scan_updated.connect(self.playground_tab.refresh_playground)
        self.scan_control_tab.cwd_changed.connect(self.on_cwd_changed)
        self.scan_control_tab.theme_changed.connect(self.apply_theme)
        
        self.apply_theme()

    def on_cwd_changed(self, new_path):
        self.working_directory = new_path
        self.playground_tab.set_working_directory(new_path)
        self.terminal_tab.set_working_directory(new_path)
        command_db.set_setting('last_cwd', new_path)

    def apply_theme(self):
        theme_name = command_db.get_setting('active_theme')
        stylesheet = command_db.get_setting(f"{theme_name}_theme_stylesheet")
        if stylesheet:
            self.setStyleSheet(stylesheet)
            # Safe check in case scan_control hasn't fully loaded
            if hasattr(self, 'scan_control_tab'):
                self.scan_control_tab.apply_theme(theme_name)
            if hasattr(self, 'playground_tab'):
                self.playground_tab.apply_theme()

    def closeEvent(self, event):
        if hasattr(self, 'terminal_tab'):
            self.terminal_tab.stop_all_processes()
        if hasattr(self, 'scan_control_tab') and self.scan_control_tab.worker and self.scan_control_tab.worker.isRunning():
            self.scan_control_tab.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    command_db.initialize_db()

    # 1. Run the Startup Wizard first
    wizard = StartupWizard()
    
    # 2. If the user finished the wizard (clicked a button), launch the main app
    if wizard.exec_() == QDialog.Accepted:
        # Pass the selected engagement type to the main window
        main_win = CyberSecBuddyApp(engagement_type=wizard.engagement_type)
        main_win.show()
        sys.exit(app.exec_())
    else:
        # User closed the wizard without selecting; exit app
        sys.exit()