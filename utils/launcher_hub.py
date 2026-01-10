import os
import random
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QFrame, QGridLayout, QScrollArea, 
                             QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QCursor, QColor, QMovie, QPixmap

# ---------------------------------------------------------
# 1. INTERACTIVE POKEMON LABEL
# ---------------------------------------------------------
class InteractivePokemonLabel(QLabel):
    def __init__(self, asset_base_path, parent=None):
        super().__init__(parent)
        self.asset_base_path = asset_base_path
        self.current_movie = None
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(100, 100)
        self.setStyleSheet("background: transparent;")
        
        self.heart_lbl = QLabel(self)
        self.heart_lbl.setFixedSize(32, 32)
        self.heart_lbl.move(60, 10) 
        self.heart_lbl.hide()
        
        # Robust Heart Loading
        self.heart_pixmap = None
        potential_heart_paths = [
            os.path.join(self.asset_base_path, "themes", "pokemon_assets", "heart.png"),
            os.path.join(self.asset_base_path, "resources", "img", "heart.png"),
            os.path.join(self.asset_base_path, "heart.png")
        ]
        
        for p in potential_heart_paths:
            if os.path.exists(p):
                self.heart_pixmap = QPixmap(p).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.heart_lbl.setPixmap(self.heart_pixmap)
                break
        
        if not self.heart_pixmap:
             self.heart_lbl.setStyleSheet("background-color: #ff5555; border-radius: 16px; border: 2px solid white;")

        self.heart_timer = QTimer(self)
        self.heart_timer.setSingleShot(True)
        self.heart_timer.timeout.connect(self.heart_lbl.hide)
        
        self.load_random_pokemon()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pet_pokemon()
        super().mousePressEvent(event)

    def pet_pokemon(self):
        self.heart_lbl.show()
        self.heart_lbl.raise_()
        self.heart_timer.start(1500) 

    def load_random_pokemon(self):
        possible_roots = [
            os.path.join(self.asset_base_path, "themes", "pokemon_assets"),
            os.path.join(self.asset_base_path, "resources", "img", "pokemon"),
        ]
        
        found_root = None
        for root in possible_roots:
            if os.path.exists(root):
                found_root = root
                break
        
        if not found_root:
            self.setText("No Assets")
            return

        try:
            all_gifs = []
            for dirpath, _, filenames in os.walk(found_root):
                for f in filenames:
                    if f.lower().endswith(".gif"):
                        all_gifs.append(os.path.join(dirpath, f))
            
            if not all_gifs:
                self.setText("No GIFs")
                return

            gif_path = random.choice(all_gifs)
            
            if self.current_movie:
                self.current_movie.stop()
                self.current_movie.deleteLater()

            self.current_movie = QMovie(gif_path)
            self.current_movie.setScaledSize(QSize(80, 80))
            self.setMovie(self.current_movie)
            self.current_movie.start()
            self.setText("") 

        except Exception as e:
            print(f"Error loading Pokemon: {e}")
            self.setText("Error")

# ---------------------------------------------------------
# 2. TOOL CARD
# ---------------------------------------------------------
class ToolCard(QFrame):
    clicked = pyqtSignal(str) 

    def __init__(self, title, description, module_id, theme_color, bg_color, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        # Slightly reduced height to fit 5 in a column nicely
        self.setFixedSize(280, 160) 
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setObjectName("ToolCard")
        
        self.setStyleSheet(f"""
            #ToolCard {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {bg_color}, stop:1 #2f2f40);
                border: 2px solid #4a4a5e;
                border-radius: 12px;
            }}
            #ToolCard:hover {{
                border: 2px solid {theme_color};
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {bg_color}, stop:1 #38384a);
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 16, QFont.Bold))
        lbl_title.setStyleSheet("color: #ffffff; background: transparent;")
        
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(QFont("Arial", 9))
        lbl_desc.setStyleSheet("color: #d0d0e0; background: transparent;")
        lbl_desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        lbl_launch = QLabel("OPEN ➔")
        lbl_launch.setFont(QFont("Arial", 8, QFont.Bold))
        lbl_launch.setStyleSheet(f"color: {theme_color}; background: transparent;")
        
        layout.addWidget(lbl_title)
        layout.addSpacing(5)
        layout.addWidget(lbl_desc)
        layout.addStretch()
        layout.addWidget(lbl_launch, alignment=Qt.AlignRight)

    def mousePressEvent(self, event):
        self.clicked.emit(self.module_id)

# ---------------------------------------------------------
# 3. APP LAUNCHER (THE HUB)
# ---------------------------------------------------------
class AppLauncher(QMainWindow):
    launch_module_signal = pyqtSignal(str) 

    def __init__(self, project_name, base_asset_path):
        super().__init__()
        self.project_name = project_name
        self.base_asset_path = base_asset_path 
        
        self.setWindowTitle("CyberSec Suite Hub")
        self.resize(1280, 900)
        self.setStyleSheet("QMainWindow { background-color: #20202a; }")
        
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.setup_header()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #20202a; } 
            QWidget { background: #20202a; }
            QScrollBar:vertical { width: 10px; background: #2f2f40; }
            QScrollBar::handle:vertical { background: #555; border-radius: 5px; }
        """)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(50, 40, 50, 60)
        
        self.setup_apps_masonry()
        
        scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(scroll)
        self.setup_footer()

    def setup_header(self):
        header = QFrame()
        header.setFixedHeight(140) 
        header.setStyleSheet("background-color: #1a1a24; border-bottom: 1px solid #333;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(50, 0, 50, 0)
        
        text_layout = QVBoxLayout()
        text_layout.setAlignment(Qt.AlignVCenter)
        
        lbl_title = QLabel("MISSION CONTROL")
        lbl_title.setFont(QFont("Arial", 28, QFont.Bold))
        lbl_title.setStyleSheet("color: #ffffff; letter-spacing: 2px;")
        
        lbl_ctx = QLabel(f"OPERATION: {self.project_name.upper()}")
        lbl_ctx.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 14px; font-family: 'Courier New';")
        
        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_ctx)
        
        layout.addLayout(text_layout)
        layout.addStretch()

        companion_frame = QFrame()
        companion_frame.setFixedSize(140, 120)
        companion_frame.setStyleSheet("background-color: #252530; border: 1px solid #444; border-radius: 10px;")
        comp_layout = QVBoxLayout(companion_frame)
        comp_layout.setAlignment(Qt.AlignCenter)
        
        self.poke_label = InteractivePokemonLabel(self.base_asset_path)
        comp_layout.addWidget(self.poke_label)
        
        layout.addWidget(companion_frame)
        self.main_layout.addWidget(header)

    def setup_apps_masonry(self):
        """
        Organize apps into 3 optimized columns to avoid empty space.
        Balance: 5 items per column.
        """
        categories = {
            "RECONNAISSANCE": [
                ("Scan Control", "Nmap automation & Target discovery.", "scan", "#00d2ff", "#0a2a33"),
            ],
            "ENUMERATION": [
                ("Enumeration", "Service enumeration tools (HTTP/SMB).", "enum", "#2ecc71", "#0d331c"),
                ("Active Directory", "Bloodhound integration & LDAP.", "ad", "#5dade2", "#112233"),
                ("Threat Model", "Attack vector mapping & planning.", "threat", "#f1c40f", "#332b0a"),
                ("Playground", "Scratchpad & Manual testing.", "play", "#95a5a6", "#222222"),
            ],
            "EXPLOITING": [
                ("Exploitation", "Metasploit & Custom exploits.", "exploit", "#e74c3c", "#33120e"),
                ("Brute Force", "Hydra/Medusa dictionary attacks.", "brute", "#9b59b6", "#260e33"),
                ("Payload Gen", "Msfvenom payload automation.", "payload", "#8e44ad", "#1c0d24"),
                ("C2 Framework", "Listeners, Reverse Shells.", "c2", "#3498db", "#0e2633"),
                ("CVE Search", "Vulnerability database lookup.", "cve", "#ff7f50", "#33160a"),
            ],
            "PRIVESC & POST-EXPLOTAION": [
                ("Privilege Esc", "Privesc checks (LinPEAS/WinPEAS).", "privesc", "#ff007f", "#330019"),
                ("Post Exploitation", "Persistence, Looting, & Scripts.", "postexp", "#d35400", "#331a00"),
            ],
            "REPORTING": [
                 ("Reporting", "Generate HTML/PDF finding reports.", "report", "#e67e22", "#331c07"),
            ],
            "OTHERS": [
                ("Dashboard", "Project overview & Stats.", "dashboard", "#ffffff", "#333333"),
                ("Project Settings", "Edit scope, client info & config.", "settings", "#7f8c8d", "#2c3e50"),
            ]
        }

        # 3-Column Layout
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(40)
        cols_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Define which categories go into which column to balance the height
        # Column 1: Recon (1) + Enum (4) = 5 Items
        # Column 2: Exploiting (5) = 5 Items
        # Column 3: Privesc (2) + Reporting (1) + Others (2) = 5 Items
        columns_map = [
            ["RECONNAISSANCE", "ENUMERATION"],
            ["EXPLOITING"],
            ["PRIVESC & POST-EXPLOTAION", "REPORTING", "OTHERS"]
        ]

        for col_cats in columns_map:
            col_widget = QWidget()
            col_layout = QVBoxLayout(col_widget)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(15)
            col_layout.setAlignment(Qt.AlignTop)
            
            for cat_key in col_cats:
                # Section Header
                lbl_header = QLabel(cat_key)
                lbl_header.setFont(QFont("Arial", 12, QFont.Bold))
                lbl_header.setStyleSheet("color: #666688; margin-top: 10px; margin-bottom: 5px; letter-spacing: 1px;")
                col_layout.addWidget(lbl_header)

                # Cards in this category
                for title, desc, mid, accent, bg in categories[cat_key]:
                    card = ToolCard(title, desc, mid, accent, bg)
                    card.clicked.connect(self.on_card_clicked)
                    col_layout.addWidget(card)
            
            col_layout.addStretch()
            cols_layout.addWidget(col_widget)

        self.content_layout.addLayout(cols_layout)

    def setup_footer(self):
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background-color: #1a1a24; border-top: 1px solid #333;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(30, 0, 30, 0)
        self.main_layout.addWidget(footer)

    def on_card_clicked(self, module_id):
        self.launch_module_signal.emit(module_id)
