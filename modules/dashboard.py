import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGridLayout, QProgressBar, QScrollArea, QPushButton,
    QSizePolicy, QStyle, QStyleOption
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPalette, QPainter, QPixmap

from utils import project_db

# ---------------------------------------------------------
# 1. UI COMPONENTS
# ---------------------------------------------------------

class BigStatCard(QFrame):
    """A large, high-impact stat card for the upper dashboard."""
    def __init__(self, title, value, color="#00d2ff", icon=None):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(40, 40, 60, 150);
                border: 1px solid #4a4a5e;
                border-radius: 12px;
            }}
            QLabel#Title {{
                color: #aaaaaa;
                font-size: 14px;
                font-weight: bold;
                text-transform: uppercase;
                background-color: transparent;
                border: none;
            }}
            QLabel#Value {{
                color: {color};
                font-size: 42px; 
                font-weight: 900;
                font-family: 'Arial Black', 'Arial';
                background-color: transparent;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        lbl_val = QLabel(str(value)); lbl_val.setObjectName("Value")
        lbl_val.setAlignment(Qt.AlignCenter)
        
        lbl_tit = QLabel(title); lbl_tit.setObjectName("Title")
        lbl_tit.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(lbl_val)
        layout.addWidget(lbl_tit)

class ProgressStepItem(QFrame):
    """A row representing a Recon step (e.g., Naabu Scan)."""
    def __init__(self, name, completed):
        super().__init__()
        # Dynamic color based on status
        bg = "rgba(40, 167, 69, 30)" if completed else "rgba(255, 255, 255, 10)"
        border = "#28a745" if completed else "#444"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border-left: 4px solid {border};
                border-radius: 4px;
                margin-bottom: 4px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0; background: transparent; border: none;")
        
        status_text = "✔ COMPLETED" if completed else "○ PENDING"
        status_color = "#28a745" if completed else "#888"
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold; font-size: 12px; background: transparent; border: none;")
        
        layout.addWidget(lbl_name)
        layout.addStretch()
        layout.addWidget(lbl_status)

class ServiceEnumItem(QFrame):
    """A row representing Enumeration progress for a specific service."""
    def __init__(self, name, done, total, percent):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background-color: #252535;
                border-radius: 6px;
                margin-bottom: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Header
        top = QHBoxLayout()
        lbl_name = QLabel(name.upper())
        lbl_name.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 14px; background: transparent; border: none;")
        
        lbl_count = QLabel(f"{done} / {total} Targets")
        lbl_count.setStyleSheet("color: #aaa; font-size: 12px; background: transparent; border: none;")
        
        top.addWidget(lbl_name)
        top.addStretch()
        top.addWidget(lbl_count)
        
        # Progress Bar
        bar = QProgressBar()
        bar.setValue(percent)
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #1a1a25;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d2ff, stop:1 #0055ff);
                border-radius: 4px;
            }
        """)
        
        layout.addLayout(top)
        layout.addWidget(bar)

# ---------------------------------------------------------
# 2. MAIN DASHBOARD WIDGET
# ---------------------------------------------------------

class DashboardWidget(QWidget):
    def __init__(self, project_db_path=None, hostname_test=False, parent=None):
        super().__init__(parent)
        self.project_db_path = project_db_path

        # --- Background Image Logic ---
        self.bg_pixmap = None
        if hostname_test:
            # Navigate to themes/img/pokemon/dashboard_bg.png (or use the playground one)
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            bg_path = os.path.join(base_path, "themes", "img", "pokemon", "dashboard_bg.png")
            
            if os.path.exists(bg_path):
                self.bg_pixmap = QPixmap(bg_path)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(25)

        # =========================================================
        # UPPER HALF: HERO SECTION (Project Info & Big Stats)
        # =========================================================
        self.hero_frame = QFrame()
        self.hero_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        hero_bg = "rgba(30, 30, 47, 180)" if self.bg_pixmap else "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e1e2f, stop:1 #252535)"
        self.hero_frame.setStyleSheet(f"""
            QFrame#Hero {{
                background-color: {hero_bg};
                border: 2px solid #4a4a5e;
                border-radius: 20px;
            }}
        """)
        self.hero_frame.setObjectName("Hero")
        
        hero_layout = QVBoxLayout(self.hero_frame)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        hero_layout.setSpacing(20)

        # -- Row 1: Client Name & Metadata --
        meta_layout = QHBoxLayout()
        
        # Left: Client Name
        self.lbl_client = QLabel("CLIENT NAME")
        self.lbl_client.setStyleSheet("font-size: 48px; font-weight: 900; color: white; background: transparent; border: none;")
        
        # Right: Type & Deadline
        meta_right_layout = QVBoxLayout()
        self.lbl_type = QLabel("Engagement: Pentest")
        self.lbl_type.setStyleSheet("font-size: 18px; color: #00d2ff; font-weight: bold; background: transparent; border: none;")
        self.lbl_type.setAlignment(Qt.AlignRight)
        
        self.lbl_deadline = QLabel("Deadline: YYYY-MM-DD")
        self.lbl_deadline.setStyleSheet("font-size: 16px; color: #ff5555; background: transparent; border: none;")
        self.lbl_deadline.setAlignment(Qt.AlignRight)
        
        meta_right_layout.addWidget(self.lbl_type)
        meta_right_layout.addWidget(self.lbl_deadline)
        
        meta_layout.addWidget(self.lbl_client)
        meta_layout.addStretch()
        meta_layout.addLayout(meta_right_layout)
        
        hero_layout.addLayout(meta_layout)
        
        # -- Row 2: Divider --
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #4a4a5e; border: none; max-height: 2px;")
        hero_layout.addWidget(line)

        # -- Row 3: Big Stats Grid --
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.card_scope = BigStatCard("Scope Size", "0", "#00ff00")
        self.card_creds = BigStatCard("Credentials Found", "0", "#ffaa00")
        self.card_progress = BigStatCard("Overall Completion", "0%", "#00d2ff")
        
        stats_layout.addWidget(self.card_scope)
        stats_layout.addWidget(self.card_creds)
        stats_layout.addWidget(self.card_progress)
        
        hero_layout.addLayout(stats_layout)
        
        # Add Hero to Main Layout
        self.main_layout.addWidget(self.hero_frame, stretch=2) # Higher stretch = takes more space

        # =========================================================
        # LOWER HALF: PROGRESS TRACKER
        # =========================================================
        
        # Container for lower part
        lower_container = QWidget()
        lower_container.setAttribute(Qt.WA_TranslucentBackground)
        lower_layout = QHBoxLayout(lower_container)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(30)

        # -- Column 1: Recon Steps --
        col_recon = QFrame()
        col_recon.setStyleSheet("background-color: transparent;")
        v_recon = QVBoxLayout(col_recon)
        v_recon.setContentsMargins(0,0,0,0)
        v_recon.addWidget(QLabel("RECONNAISSANCE CHECKLIST", styleSheet="color: #888; font-weight: 900; font-size: 14px; margin-bottom: 10px;"))
        
        self.scroll_recon = QScrollArea()
        self.scroll_recon.setWidgetResizable(True)
        self.scroll_recon.setStyleSheet("background-color: transparent; border: none;")
        self.content_recon = QWidget()
        self.layout_recon_items = QVBoxLayout(self.content_recon)
        self.layout_recon_items.setAlignment(Qt.AlignTop)
        self.scroll_recon.setWidget(self.content_recon)
        
        v_recon.addWidget(self.scroll_recon)

        # -- Column 2: Enumeration Steps --
        col_enum = QFrame()
        col_enum.setStyleSheet("background-color: transparent;")
        v_enum = QVBoxLayout(col_enum)
        v_enum.setContentsMargins(0,0,0,0)
        v_enum.addWidget(QLabel("SERVICE ENUMERATION PROGRESS", styleSheet="color: #888; font-weight: 900; font-size: 14px; margin-bottom: 10px;"))
        
        self.scroll_enum = QScrollArea()
        self.scroll_enum.setWidgetResizable(True)
        self.scroll_enum.setStyleSheet("background-color: transparent; border: none;")
        self.content_enum = QWidget()
        self.layout_enum_items = QVBoxLayout(self.content_enum)
        self.layout_enum_items.setAlignment(Qt.AlignTop)
        self.scroll_enum.setWidget(self.content_enum)
        
        v_enum.addWidget(self.scroll_enum)

        lower_layout.addWidget(col_recon)
        lower_layout.addWidget(col_enum)

        self.main_layout.addWidget(lower_container, stretch=3)

        # Refresh Button (Floating bottom right feels)
        btn_refresh = QPushButton("↻ Refresh Dashboard")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_data)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #3e3e50; 
                color: #aaa; 
                font-weight: bold;
                padding: 10px; 
                border-radius: 5px; 
                border: 1px solid #4a4a5e;
            }
            QPushButton:hover {
                color: white;
                border-color: #00d2ff;
            }
        """)
        self.main_layout.addWidget(btn_refresh, alignment=Qt.AlignRight)

    def paintEvent(self, event):
        """Override paintEvent to draw the background image."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        
        if self.bg_pixmap and not self.bg_pixmap.isNull():
            # Draw the background image scaled to the current widget size
            p.drawPixmap(self.rect(), self.bg_pixmap)
        else:
            # Default behavior if no image is present
            self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def load_data(self):
        if not self.project_db_path: return
        
        data = project_db.get_dashboard_stats(self.project_db_path)
        
        # 1. Update Hero
        self.lbl_client.setText(data['client'].upper())
        self.lbl_type.setText(f"ENGAGEMENT: {data['type'].upper()}")
        self.lbl_deadline.setText(f"DEADLINE: {data['deadline']}")
        
        self.card_scope.findChild(QLabel, "Value").setText(str(data['scope_count']))
        self.card_creds.findChild(QLabel, "Value").setText(str(data['creds_count']))
        self.card_progress.findChild(QLabel, "Value").setText(f"{data['overall_progress']}%")
        
        # 2. Update Recon List
        self.clear_layout(self.layout_recon_items)
        if not data['recon_steps']:
            self.layout_recon_items.addWidget(QLabel("No recon steps initialized.", styleSheet="color:#666;"))
        else:
            for step in data['recon_steps']:
                item = ProgressStepItem(step['step'], step['completed'])
                self.layout_recon_items.addWidget(item)

        # 3. Update Enum List
        self.clear_layout(self.layout_enum_items)
        if not data['enum_services']:
            self.layout_enum_items.addWidget(QLabel("No services discovered yet.\nRun Threat Modeling to populate.", styleSheet="color:#666; font-style:italic;"))
        else:
            for svc in data['enum_services']:
                item = ServiceEnumItem(svc['name'], svc['done'], svc['total'], svc['percent'])
                self.layout_enum_items.addWidget(item)

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def refresh_view(self):
        """Called by Main Window when tab is switched."""
        self.load_data()