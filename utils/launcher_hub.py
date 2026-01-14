import os
import sys # Added for folder opening
import subprocess # Added for folder opening on Linux/Mac
import random
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QFrame, QGridLayout, QScrollArea, 
                             QGraphicsDropShadowEffect, QMenu, QAction, QPushButton, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QSettings
from PyQt5.QtGui import QFont, QCursor, QColor, QMovie, QPixmap, QBrush, QPalette

# ---------------------------------------------------------
# 1. INTERACTIVE POKEMON LABEL (Selectable Folder)
# ---------------------------------------------------------
class InteractivePokemonLabel(QLabel):
    def __init__(self, asset_base_path, parent=None):
        super().__init__(parent)
        self.asset_base_path = asset_base_path
        self.current_movie = None
        
        # Persistent Settings (To remember your folder choice)
        self.settings = QSettings("CyberSecBuddy", "MascotConfig")

        # --- PATH DEFINITIONS ---
        # 1. Safe Default (Shipped with App)
        self.default_path = os.path.join(self.asset_base_path, "resources", "img", "mascot")
        
        # 2. Hardcoded User Override (Legacy support)
        self.legacy_custom_path = os.path.join(self.asset_base_path, "themes", "pokemon_assets")
        
        # UI Setup
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(120, 120)
        self.setStyleSheet("background: transparent;")
        
        # --- Reaction Icon (Heart) ---
        self.heart_lbl = QLabel(self)
        self.heart_lbl.setFixedSize(32, 32)
        self.heart_lbl.move(80, 10) 
        self.heart_lbl.hide()
        
        # Initialize Heart Icon
        self.update_heart_icon()

        self.heart_timer = QTimer(self)
        self.heart_timer.setSingleShot(True)
        self.heart_timer.timeout.connect(self.heart_lbl.hide)
        
        # Load immediately
        self.load_random_pokemon()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pet_pokemon()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        # Action 1: Cycle to next GIF
        reload_action = QAction("🔄 Next Mascot", self)
        reload_action.triggered.connect(self.load_random_pokemon)
        menu.addAction(reload_action)
        
        menu.addSeparator()

        # Action 2: Change the source folder
        change_folder_action = QAction("📂 Select Mascot Folder...", self)
        change_folder_action.triggered.connect(self.select_custom_folder)
        menu.addAction(change_folder_action)

        # Action 3: Reset to Default
        reset_action = QAction("❌ Reset to Default", self)
        reset_action.triggered.connect(self.reset_to_default)
        menu.addAction(reset_action)
        
        menu.exec_(event.globalPos())

    def pet_pokemon(self):
        self.heart_lbl.show()
        self.heart_lbl.raise_()
        self.heart_timer.start(1500) 

    def select_custom_folder(self):
        """Opens a dialog for the user to pick any folder on their PC."""
        folder = QFileDialog.getExistingDirectory(self, "Select Mascot Assets Folder")
        if folder:
            # Save the path to settings
            self.settings.setValue("custom_mascot_path", folder)
            # Reload immediately
            self.load_random_pokemon()
            self.update_heart_icon()

    def reset_to_default(self):
        """Clears the user's custom selection."""
        self.settings.remove("custom_mascot_path")
        self.load_random_pokemon()
        self.update_heart_icon()

    def get_active_folder(self):
        """
        Determines priority:
        1. User's Selected Folder (via Menu)
        2. Hardcoded 'themes/pokemon_assets' (if valid)
        3. Default 'resources/img/mascot'
        """
        # 1. Check Saved Setting
        saved_path = self.settings.value("custom_mascot_path")
        if saved_path and os.path.exists(saved_path):
             return saved_path

        # 2. Check Legacy Folder
        if os.path.exists(self.legacy_custom_path):
            # Verify it actually has content
            for root, dirs, files in os.walk(self.legacy_custom_path):
                for f in files:
                    if f.lower().endswith('.gif'):
                        return self.legacy_custom_path

        # 3. Fallback
        return self.default_path

    def update_heart_icon(self):
        """Refresh the heart icon based on the active folder."""
        folder = self.get_active_folder()
        heart_path = os.path.join(folder, "heart.png")
        
        # Check specific folder first, then default fallback
        if not os.path.exists(heart_path):
            heart_path = os.path.join(self.default_path, "heart.png")

        if os.path.exists(heart_path):
            self.heart_lbl.setPixmap(QPixmap(heart_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.heart_lbl.setStyleSheet("background: transparent;")
        else:
            self.heart_lbl.setPixmap(QPixmap())
            self.heart_lbl.setStyleSheet("background-color: #ff5555; border-radius: 16px; border: 2px solid white;")

    def open_current_folder(self):
        """Legacy helper if you still want the button to open the folder."""
        folder = self.get_active_folder()
        if not os.path.exists(folder): return
        try:
            if sys.platform == 'win32': os.startfile(folder)
            elif sys.platform == 'darwin': subprocess.call(['open', folder])
            else: subprocess.call(['xdg-open', folder])
        except: pass

    def load_random_pokemon(self):
        target_folder = self.get_active_folder()

        if not os.path.exists(target_folder):
            self.setText("No Path")
            return

        try:
            gifs = []
            # RECURSIVE SEARCH: Finds gifs in Gen1/Gen2 subfolders
            for root, dirs, files in os.walk(target_folder):
                for file in files:
                    if file.lower().endswith(".gif"):
                        gifs.append(os.path.join(root, file))
            
            if not gifs:
                # If selected folder is empty, try reverting to default temporarily
                if target_folder != self.default_path:
                    self.settings.remove("custom_mascot_path") # Auto-reset bad path
                    self.load_random_pokemon() # Retry
                    return
                self.setText("No GIFs")
                return

            gif_path = random.choice(gifs)
            
            if self.current_movie:
                self.current_movie.stop()
                self.current_movie.deleteLater()

            self.current_movie = QMovie(gif_path)
            self.current_movie.setCacheMode(QMovie.CacheAll)
            self.current_movie.setScaledSize(QSize(100, 100))
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
        self.setFixedSize(240, 160) 
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
        layout.setContentsMargins(15, 15, 15, 15)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_title.setStyleSheet("color: #ffffff; background: transparent;")
        lbl_title.setWordWrap(True)
        
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(QFont("Arial", 9))
        lbl_desc.setStyleSheet("color: #b0b0c0; background: transparent;")
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
            QScrollBar:horizontal { height: 10px; background: #2f2f40; }
            QScrollBar::handle:horizontal { background: #555; border-radius: 5px; }
            QScrollBar:vertical { width: 10px; background: #2f2f40; }
            QScrollBar::handle:vertical { background: #555; border-radius: 5px; }
        """)
        
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 40, 30, 60)
        self.content_layout.setSpacing(20)
        self.content_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.setup_apps_columns()
        
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

        # --- COMPANION FRAME ---
        companion_frame = QFrame()
        companion_frame.setFixedSize(140, 130) # Height increased slightly for buttons
        companion_frame.setStyleSheet("background-color: #252530; border: 1px solid #444; border-radius: 10px;")
        
        comp_layout = QVBoxLayout(companion_frame)
        comp_layout.setAlignment(Qt.AlignCenter)
        comp_layout.setSpacing(2)
        comp_layout.setContentsMargins(5, 5, 5, 5)
        
        # 1. The Mascot Label
        self.poke_label = InteractivePokemonLabel(self.base_asset_path)
        comp_layout.addWidget(self.poke_label)
        
        # 2. NEW: Control Buttons (Cycle | Open Folder)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        # Cycle Button
        btn_next = QPushButton("⟳")
        btn_next.setToolTip("Cycle to next mascot")
        btn_next.setFixedSize(25, 20)
        btn_next.setCursor(Qt.PointingHandCursor)
        btn_next.setStyleSheet("QPushButton { background: #3a3a4a; color: #aaa; border: none; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #00d2ff; color: white; }")
        btn_next.clicked.connect(self.poke_label.load_random_pokemon)
        
        # Folder Button
        btn_folder = QPushButton("📂")
        btn_folder.setToolTip("Open assets folder")
        btn_folder.setFixedSize(25, 20)
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.setStyleSheet("QPushButton { background: #3a3a4a; color: #aaa; border: none; border-radius: 4px; } QPushButton:hover { background: #00d2ff; color: white; }")
        btn_folder.clicked.connect(self.poke_label.open_current_folder)
        
        btn_layout.addWidget(btn_next)
        btn_layout.addWidget(btn_folder)
        comp_layout.addLayout(btn_layout)
        
        layout.addWidget(companion_frame)
        self.main_layout.addWidget(header)

    def setup_apps_columns(self):
        """
        Organize apps into 5 distinct vertical columns.
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
                 ("Reportin", "Generate HTML/PDF finding reports.", "report", "#e67e22", "#331c07"),
            ],
            "OTHERS": [
                ("Dashboard", "Project overview & Stats.", "dashboard", "#ffffff", "#333333"),
                ("Project Settings", "Edit scope, client info & config.", "settings", "#7f8c8d", "#2c3e50"),
            ]
        }

        # Create 5 Vertical Layouts
        for cat_name, apps in categories.items():
            col_container = QWidget()
            col_container.setFixedWidth(250) 
            col_layout = QVBoxLayout(col_container)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(15)
            col_layout.setAlignment(Qt.AlignTop)

            # 1. Header
            lbl_header = QLabel(cat_name)
            lbl_header.setFont(QFont("Arial", 11, QFont.Bold))
            lbl_header.setStyleSheet("color: #8888aa; text-transform: uppercase; margin-bottom: 5px; border-bottom: 2px solid #333; padding-bottom: 5px;")
            lbl_header.setWordWrap(True) 
            col_layout.addWidget(lbl_header)

            # 2. App Cards
            for title, desc, mid, accent, bg in apps:
                card = ToolCard(title, desc, mid, accent, bg)
                card.clicked.connect(self.on_card_clicked)
                col_layout.addWidget(card)
            
            col_layout.addStretch()
            self.content_layout.addWidget(col_container)

    def setup_footer(self):
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background-color: #1a1a24; border-top: 1px solid #333;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(30, 0, 30, 0)
        self.main_layout.addWidget(footer)

    def on_card_clicked(self, module_id):
        self.launch_module_signal.emit(module_id)