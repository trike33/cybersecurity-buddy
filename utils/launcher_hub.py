import os
import random
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QFrame, QGridLayout, QScrollArea, 
                             QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QCursor, QColor, QMovie, QPixmap, QPainter, QBrush

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
        
        # Heart Overlay
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
        
        # Fallback if no heart image found: Draw a red circle placeholder
        if not self.heart_pixmap:
            self.heart_lbl.setStyleSheet("background-color: #ff5555; border-radius: 16px; border: 2px solid white;")

        self.heart_timer = QTimer(self)
        self.heart_timer.setSingleShot(True)
        self.heart_timer.timeout.connect(self.heart_lbl.hide)
        
        # Load the Pokemon
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
        # 1. Define potential root directories for Pokemon assets
        # We check both the 'themes' structure (from main.py) and 'resources' structure
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
            print(f"DEBUG: Could not find Pokemon assets in {possible_roots}")
            return

        try:
            # 2. Walk the directory to find GIFs
            # This handles both "Gen 5" folders and flat lists
            all_gifs = []
            for dirpath, _, filenames in os.walk(found_root):
                for f in filenames:
                    if f.lower().endswith(".gif"):
                        all_gifs.append(os.path.join(dirpath, f))
            
            if not all_gifs:
                self.setText("No GIFs")
                return

            # 3. Pick one and play
            gif_path = random.choice(all_gifs)
            
            if self.current_movie:
                self.current_movie.stop()
                self.current_movie.deleteLater()

            self.current_movie = QMovie(gif_path)
            self.current_movie.setScaledSize(QSize(80, 80))
            self.setMovie(self.current_movie)
            self.current_movie.start()
            self.setText("") # Clear any text

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
        self.setFixedSize(300, 200)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setObjectName("ToolCard")
        
        self.setStyleSheet(f"""
            #ToolCard {{
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 {bg_color}, stop:1 #2f2f40);
                border: 2px solid #4a4a5e;
                border-radius: 16px;
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
        layout.setContentsMargins(25, 25, 25, 25)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 18, QFont.Bold))
        lbl_title.setStyleSheet("color: #ffffff; background: transparent;")
        
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(QFont("Arial", 10))
        lbl_desc.setStyleSheet("color: #d0d0e0; background: transparent;")
        lbl_desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        lbl_launch = QLabel("OPEN TOOL ➔")
        lbl_launch.setFont(QFont("Arial", 9, QFont.Bold))
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
        self.resize(1200, 900)
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
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setContentsMargins(60, 60, 60, 60)
        self.grid_layout.setSpacing(40)
        
        self.setup_apps_grid()
        
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

    def setup_apps_grid(self):
        # (Title, Description, ID, Accent Color, Dark BG Tint)
        apps = [
            ("Dashboard", "Project overview & Stats.", "dashboard", "#ffffff", "#333333"),
            ("Scan Control", "Nmap & Target discovery.", "scan", "#00d2ff", "#0a2a33"),
            ("Enumeration", "Service enumeration tools.", "enum", "#2ecc71", "#0d331c"),
            ("Threat Model", "Attack vector mapping.", "threat", "#f1c40f", "#332b0a"),
            ("Exploitation", "Metasploit & custom exploits.", "exploit", "#e74c3c", "#33120e"),
            ("Brute Force", "Hydra/Medusa manager.", "brute", "#9b59b6", "#260e33"),
            ("C2 Post", "Listeners & Shells.", "c2", "#3498db", "#0e2633"),
            ("Privilege Esc", "Privesc check scripts.", "privesc", "#ff007f", "#330019"),
            ("Active Directory", "Bloodhound & LDAP.", "ad", "#5dade2", "#112233"),
            ("MITM / Relay", "Responder & Spoofing.", "mitm", "#fdcb6e", "#332811"),
            ("CVE Search", "Vulnerability database.", "cve", "#ff7f50", "#33160a"),
            ("Payload Gen", "Msfvenom automation.", "payload", "#8e44ad", "#1c0d24"),
            ("Reporting", "Generate HTML/PDF reports.", "report", "#e67e22", "#331c07"),
            ("Playground", "Scratchpad & Manual testing.", "play", "#95a5a6", "#222222"),
        ]

        row, col = 0, 0
        for title, desc, mid, accent, bg in apps:
            card = ToolCard(title, desc, mid, accent, bg)
            card.clicked.connect(self.on_card_clicked)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def setup_footer(self):
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background-color: #1a1a24; border-top: 1px solid #333;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(30, 0, 30, 0)
        # Footer buttons can go here
        self.main_layout.addWidget(footer)

    def on_card_clicked(self, module_id):
        self.launch_module_signal.emit(module_id)
