import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QGridLayout, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QFont, QColor, QCursor

class ToolCard(QFrame):
    """A stylish card representing a tool/application with custom coloring."""
    clicked = pyqtSignal()

    def __init__(self, title, description, icon_name, theme_color="#00d2ff", is_enabled=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 180)
        self.is_enabled = is_enabled
        self.theme_color = theme_color
        self.setCursor(QCursor(Qt.PointingHandCursor if is_enabled else Qt.ForbiddenCursor))
        
        # Style
        self.setObjectName("ToolCard")
        # We use the theme_color for the border on hover and the status text
        self.setStyleSheet(f"""
            #ToolCard {{
                background-color: { '#2f2f40' if is_enabled else '#1e1e24' };
                border: 2px solid #4a4a5e;
                border-radius: 12px;
            }}
            #ToolCard:hover {{
                border: 2px solid { theme_color if is_enabled else '#4a4a5e' };
                background-color: { '#38384a' if is_enabled else '#1e1e24' };
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 16, QFont.Bold))
        lbl_title.setStyleSheet("color: #ffffff;" if is_enabled else "color: #555555;")
        
        # Description
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(QFont("Arial", 10))
        lbl_desc.setStyleSheet("color: #a0a0b0;" if is_enabled else "color: #555555;")
        
        # Status Badge
        lbl_status = QLabel("AVAILABLE" if is_enabled else "COMING SOON")
        lbl_status.setFont(QFont("Arial", 8, QFont.Bold))
        # This makes the "AVAILABLE" text glow with the card's theme color
        lbl_status.setStyleSheet(f"""
            color: { theme_color if is_enabled else '#555555' };
            background-color: transparent;
        """)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_desc)
        layout.addStretch()
        layout.addWidget(lbl_status, alignment=Qt.AlignRight)

    def mousePressEvent(self, event):
        if self.is_enabled:
            self.clicked.emit()
            
class AppLauncher(QMainWindow):
    def __init__(self, engagement_type, project_db_path):
        super().__init__()
        self.engagement_type = engagement_type
        self.project_db_path = project_db_path
        self.switch_project_requested = False
        
        self.setWindowTitle("CyberSec Suite Hub")
        self.resize(1000, 700)
        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.setup_header()
        self.setup_content()
        self.setup_footer()
        
        self.apply_stylesheet()

    def setup_header(self):
        header = QFrame()
        header.setFixedHeight(120)
        header.setStyleSheet("background-color: #1e1e2f; border-bottom: 1px solid #4a4a5e;")
        
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(40, 0, 40, 0)
        
        # Project Info
        info_layout = QVBoxLayout()
        info_layout.setAlignment(Qt.AlignVCenter)
        
        lbl_suite = QLabel("CYBERSEC SUITE")
        lbl_suite.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_suite.setStyleSheet("color: #00d2ff; letter-spacing: 2px;")
        
        project_name = "Unknown Project"
        if self.project_db_path:
             project_name = os.path.basename(os.path.dirname(self.project_db_path)).replace('_', ' ')
        
        lbl_proj = QLabel(project_name)
        lbl_proj.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_proj.setStyleSheet("color: #ffffff;")
        
        lbl_type = QLabel(f"Mode: {self.engagement_type}")
        lbl_type.setStyleSheet("color: #8888aa; font-style: italic;")
        
        info_layout.addWidget(lbl_suite)
        info_layout.addWidget(lbl_proj)
        info_layout.addWidget(lbl_type)
        
        h_layout.addLayout(info_layout)
        h_layout.addStretch()
        
        self.main_layout.addWidget(header)

    def setup_content(self):
        content_frame = QFrame()
        content_frame.setStyleSheet("background-color: #252535;")
        
        grid = QGridLayout(content_frame)
        grid.setContentsMargins(50, 50, 50, 50)
        grid.setSpacing(30)
        
        # --- Card 1: Main App (BLUE) ---
        self.card_main = ToolCard(
            "CyberSec Buddy", 
            "The core pentesting platform. Scanning, enumeration, exploitation, and reporting.",
            "app.png",
            theme_color="#00d2ff",  # Cyan Blue
            is_enabled=True
        )
        self.card_main.clicked.connect(self.launch_cybersec_buddy)
        
        # --- Card 2: Reporting Tool (PURPLE) ---
        self.card_report = ToolCard(
            "Report Generator", 
            "Generate PDF/HTML reports from existing databases without loading the full suite.",
            "report.png",
            theme_color="#bd00ff", # Bright Purple
            is_enabled=False 
        )
        
        # --- Card 3: Network Mapper (ORANGE) ---
        self.card_map = ToolCard(
            "Network Visualizer", 
            "3D Visualization of the network topology found during reconnaissance.",
            "map.png",
            theme_color="#ffae00", # Golden Orange
            is_enabled=False
        )

        grid.addWidget(self.card_main, 0, 0)
        grid.addWidget(self.card_report, 0, 1)
        grid.addWidget(self.card_map, 0, 2)
        
        grid.setRowStretch(1, 1) 
        self.main_layout.addWidget(content_frame)

    def setup_footer(self):
        footer = QFrame()
        footer.setFixedHeight(80)
        footer.setStyleSheet("background-color: #1e1e2f; border-top: 1px solid #4a4a5e;")
        
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(40, 0, 40, 0)
        
        btn_switch = QPushButton("⇄ Switch Project")
        btn_switch.setCursor(Qt.PointingHandCursor)
        btn_switch.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8888aa; font-weight: bold; font-size: 14px; border: none; }
            QPushButton:hover { color: #00d2ff; }
        """)
        btn_switch.clicked.connect(self.request_switch_project)
        
        btn_exit = QPushButton("Exit Suite")
        btn_exit.setCursor(Qt.PointingHandCursor)
        btn_exit.setStyleSheet("""
            QPushButton { background-color: #cf3a3a; color: white; padding: 8px 20px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #e04b4b; }
        """)
        btn_exit.clicked.connect(self.close_app)
        
        f_layout.addWidget(btn_switch)
        f_layout.addStretch()
        f_layout.addWidget(btn_exit)
        
        self.main_layout.addWidget(footer)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #252535; }
        """)

    def launch_cybersec_buddy(self):
        """
        Dynamically imports main2.py from the parent directory 
        and launches the main application window.
        """
        try:
            # 1. Get the directory containing this script (utils/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 2. Get the parent directory (root where main2.py lives)
            parent_dir = os.path.dirname(current_dir)
            
            # 3. Add parent dir to sys.path if not present
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)

            # 4. Import main2
            import main2
            
            # 5. Launch the app
            self.buddy_app = main2.CyberSecBuddyApp(
                engagement_type=self.engagement_type,
                project_db_path=self.project_db_path
            )
            self.buddy_app.showMaximized()
            self.hide() # Hide launcher
            
            # Optional: Hook into the close event if you want to re-show launcher later
            # self.buddy_app.closeEvent = ... (advanced logic)

        except ImportError as e:
            print(f"Error importing main2: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Launch Error", f"Could not find main2.py in {parent_dir}\nError: {e}")
        except Exception as e:
            print(f"Error launching app: {e}")

    def request_switch_project(self):
        self.switch_project_requested = True
        self.close()

    def close_app(self):
        self.close()