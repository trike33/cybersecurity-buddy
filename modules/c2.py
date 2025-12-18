import sys
import os
import signal
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QSplitter, 
    QTabWidget, QFormLayout, QMessageBox, QDialog, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtNetwork import QNetworkInterface, QAbstractSocket

# Import DB Manager
from utils import c2_db_manager

# ---------------------------------------------------------
# 1. PROCESS WORKER
# ---------------------------------------------------------
class ProcessWorker(QThread):
    output_received = pyqtSignal(str)
    error_received = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, command, working_dir):
        super().__init__()
        self.command = command
        self.working_dir = working_dir
        self.process = None
        self.is_running = True

    def run(self):
        try:
            self.process = subprocess.Popen(
                self.command, 
                shell=True, 
                cwd=self.working_dir,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid 
            )
            for line in iter(self.process.stdout.readline, ''):
                if not self.is_running: break
                self.output_received.emit(line.strip())
            
            self.process.stdout.close()
            self.process.wait()
            self.finished.emit()
        except Exception as e:
            self.error_received.emit(str(e))

    def write_input(self, text):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self.error_received.emit(f"Input Error: {e}")

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass 

# ---------------------------------------------------------
# 2. REUSABLE LISTENER WIDGET
# ---------------------------------------------------------
class NetcatListenerWidget(QWidget):
    """A single instance of a Netcat listener terminal."""
    def __init__(self, working_directory, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header Controls
        header = QHBoxLayout()
        self.inp_port = QLineEdit("4444")
        self.inp_port.setFixedWidth(80)
        self.btn_toggle = QPushButton("Start Listener")
        self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle_listener)
        
        header.addWidget(QLabel("Port:"))
        header.addWidget(self.inp_port)
        header.addWidget(self.btn_toggle)
        header.addStretch()
        layout.addLayout(header)
        
        # Terminal Output
        self.term_out = QTextEdit()
        self.term_out.setReadOnly(True)
        self.term_out.setStyleSheet("background-color: black; color: #00ff00; font-family: Consolas; font-size: 13px; border: 1px solid #444;")
        layout.addWidget(self.term_out)
        
        # Input
        self.term_in = QLineEdit()
        self.term_in.setPlaceholderText("Type command...")
        self.term_in.setStyleSheet("background-color: #222; color: #00ff00; font-family: Consolas; border: 1px solid #444;")
        self.term_in.returnPressed.connect(self.send_command)
        layout.addWidget(self.term_in)

    def toggle_listener(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
            self.btn_toggle.setText("Start Listener")
            self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
            self.term_out.append("\n[!] Listener Stopped.")
        else:
            port = self.inp_port.text()
            cmd = f"nc -lvnp {port}"
            self.term_out.clear()
            self.term_out.append(f"[*] Starting: {cmd}\n")
            
            self.worker = ProcessWorker(cmd, self.working_directory)
            self.worker.output_received.connect(self.term_out.append)
            self.worker.error_received.connect(self.term_out.append)
            self.worker.start()
            
            self.btn_toggle.setText("Stop Listener")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")

    def send_command(self):
        if self.worker and self.worker.isRunning():
            cmd = self.term_in.text()
            self.term_out.append(f"> {cmd}")
            self.worker.write_input(cmd)
            self.term_in.clear()

# ---------------------------------------------------------
# 3. REUSABLE SERVER WIDGET
# ---------------------------------------------------------
class FileServerWidget(QWidget):
    """A single instance of a File Server (HTTP/SMB)."""
    def __init__(self, working_directory, db_path, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.db_path = db_path
        self.worker = None
        self.init_ui()
        self.load_options()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Left Config
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        left_layout.addWidget(QLabel("1. Server Type:", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.combo_type = QComboBox()
        self.combo_type.currentIndexChanged.connect(self.update_preview)
        left_layout.addWidget(self.combo_type)
        
        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("2. Config (Port/Share):", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.inp_arg = QLineEdit()
        self.inp_arg.textChanged.connect(self.update_preview)
        left_layout.addWidget(self.inp_arg)
        
        left_layout.addSpacing(10)
        left_layout.addWidget(QLabel("3. Preview:", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.txt_preview = QTextEdit()
        self.txt_preview.setFixedHeight(60)
        self.txt_preview.setStyleSheet("background-color: #222; color: #00ff00; font-family: Consolas;")
        left_layout.addWidget(self.txt_preview)
        
        left_layout.addSpacing(15)
        self.btn_toggle = QPushButton("START SERVER")
        self.btn_toggle.setFixedHeight(40)
        self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle_server)
        left_layout.addWidget(self.btn_toggle)
        left_layout.addStretch()
        
        # Right Log
        right_panel = QGroupBox("Server Log")
        right_panel.setStyleSheet("color: #ccc;")
        right_layout = QVBoxLayout(right_panel)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #101015; color: #aaa; font-family: Consolas; font-size: 12px;")
        right_layout.addWidget(self.txt_log)
        
        layout.addWidget(left_panel, stretch=1)
        layout.addWidget(right_panel, stretch=2)

    def load_options(self):
        self.combo_type.clear()
        servers = c2_db_manager.get_servers(self.db_path)
        for s in servers:
            self.combo_type.addItem(s['name'], s)
        self.update_preview()

    def update_preview(self):
        data = self.combo_type.currentData()
        if not data: return
        arg = self.inp_arg.text()
        tmpl = data['template']
        final = tmpl.replace("{ARG}", arg if arg else data['default_arg'])
        self.inp_arg.setPlaceholderText(data['default_arg'])
        self.txt_preview.setText(final)

    def handle_log(self, text):
        ignore = ["BrokenPipeError", "Traceback", "File \"/usr", "socketserver.py"]
        if any(x in text for x in ignore): return
        self.txt_log.append(text)

    def toggle_server(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
            self.btn_toggle.setText("START SERVER")
            self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
            self.txt_log.append("\n[!] Server Stopped.")
        else:
            cmd = self.txt_preview.toPlainText().strip()
            if not cmd: return
            self.txt_log.clear()
            self.txt_log.append(f"[*] Executing: {cmd}\n")
            self.worker = ProcessWorker(cmd, self.working_directory)
            self.worker.output_received.connect(self.handle_log)
            self.worker.error_received.connect(self.handle_log)
            self.worker.start()
            self.btn_toggle.setText("STOP SERVER")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")

# ---------------------------------------------------------
# 4. MANAGER DIALOG (Existing)
# ---------------------------------------------------------
class C2ManagerDialog(QDialog):
    """Dialog to Add/Delete Payloads and Server Templates."""
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Manage C2 Database")
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QTableWidget { background-color: #2f2f40; gridline-color: #4a4a5e; color: #e0e0e0; border: 1px solid #4a4a5e; }
            QHeaderView::section { background-color: #3e3e50; color: white; padding: 4px; }
            QLineEdit { background-color: #222; color: #00ff00; border: 1px solid #555; padding: 6px; }
            QPushButton { background-color: #3e3e50; color: white; padding: 8px; border: 1px solid #555; }
            QPushButton:hover { background-color: #4e4e60; border-color: #00d2ff; }
            QTabWidget::pane { border: 1px solid #4a4a5e; }
            QTabBar::tab { background: #2f2f40; color: #aaa; padding: 8px 20px; }
            QTabBar::tab:selected { background: #00d2ff; color: #1e1e2f; font-weight: bold; }
        """)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.tab_payloads = QWidget()
        self.setup_payloads_tab()
        self.tabs.addTab(self.tab_payloads, "Reverse Shell Payloads")
        
        self.tab_servers = QWidget()
        self.setup_servers_tab()
        self.tabs.addTab(self.tab_servers, "Server Templates")
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def setup_payloads_tab(self):
        layout = QVBoxLayout(self.tab_payloads)
        
        form = QHBoxLayout()
        self.inp_p_name = QLineEdit(); self.inp_p_name.setPlaceholderText("Name (e.g. Python v2)")
        self.inp_p_tmpl = QLineEdit(); self.inp_p_tmpl.setPlaceholderText("Template (use {IP} and {PORT})")
        btn_add = QPushButton("Add"); btn_add.clicked.connect(self.add_payload)
        form.addWidget(self.inp_p_name, 1)
        form.addWidget(self.inp_p_tmpl, 3)
        form.addWidget(btn_add)
        layout.addLayout(form)
        
        self.table_p = QTableWidget()
        self.table_p.setColumnCount(3)
        self.table_p.setHorizontalHeaderLabels(["ID", "Name", "Template"])
        self.table_p.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_p.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_p)
        
        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.del_payload)
        layout.addWidget(btn_del)
        self.load_payloads()

    def setup_servers_tab(self):
        layout = QVBoxLayout(self.tab_servers)
        
        form = QHBoxLayout()
        self.inp_s_name = QLineEdit(); self.inp_s_name.setPlaceholderText("Name (e.g. Custom SMB)")
        self.inp_s_tmpl = QLineEdit(); self.inp_s_tmpl.setPlaceholderText("Template (use {ARG})")
        self.inp_s_arg = QLineEdit(); self.inp_s_arg.setPlaceholderText("Default Arg (e.g. 8000)")
        self.inp_s_arg.setFixedWidth(100)
        btn_add = QPushButton("Add"); btn_add.clicked.connect(self.add_server)
        form.addWidget(self.inp_s_name, 1)
        form.addWidget(self.inp_s_tmpl, 3)
        form.addWidget(self.inp_s_arg)
        form.addWidget(btn_add)
        layout.addLayout(form)
        
        self.table_s = QTableWidget()
        self.table_s.setColumnCount(4)
        self.table_s.setHorizontalHeaderLabels(["ID", "Name", "Template", "Def Arg"])
        self.table_s.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_s.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_s)
        
        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.del_server)
        layout.addWidget(btn_del)
        self.load_servers()

    def load_payloads(self):
        self.table_p.setRowCount(0)
        data = c2_db_manager.get_payloads(self.db_path)
        for i, row in enumerate(data):
            self.table_p.insertRow(i)
            self.table_p.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table_p.setItem(i, 1, QTableWidgetItem(row['name']))
            self.table_p.setItem(i, 2, QTableWidgetItem(row['template']))

    def load_servers(self):
        self.table_s.setRowCount(0)
        data = c2_db_manager.get_servers(self.db_path)
        for i, row in enumerate(data):
            self.table_s.insertRow(i)
            self.table_s.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table_s.setItem(i, 1, QTableWidgetItem(row['name']))
            self.table_s.setItem(i, 2, QTableWidgetItem(row['template']))
            self.table_s.setItem(i, 3, QTableWidgetItem(row['default_arg']))

    def add_payload(self):
        if c2_db_manager.add_payload(self.db_path, self.inp_p_name.text(), self.inp_p_tmpl.text()):
            self.inp_p_name.clear(); self.inp_p_tmpl.clear(); self.load_payloads()

    def del_payload(self):
        r = self.table_p.currentRow()
        if r >= 0:
            c2_db_manager.delete_payload(self.db_path, self.table_p.item(r, 0).text())
            self.load_payloads()

    def add_server(self):
        if c2_db_manager.add_server(self.db_path, self.inp_s_name.text(), self.inp_s_tmpl.text(), self.inp_s_arg.text()):
            self.inp_s_name.clear(); self.inp_s_tmpl.clear(); self.load_servers()

    def del_server(self):
        r = self.table_s.currentRow()
        if r >= 0:
            c2_db_manager.delete_server(self.db_path, self.table_s.item(r, 0).text())
            self.load_servers()

# ---------------------------------------------------------
# 5. C2 MAIN WIDGET
# ---------------------------------------------------------
class C2Widget(QWidget):
    def __init__(self, working_directory, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resources_dir = os.path.join(base_dir, "resources")
        if not os.path.exists(resources_dir): os.makedirs(resources_dir)
        self.db_path = c2_db_manager.initialize_c2_db(resources_dir)
        
        self.listeners = [] # Track listener widgets
        self.servers = []   # Track server widgets
        
        self.init_ui()
        self.refresh_ips()
        self.load_payload_options()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Stylesheet: Larger padding and min-width for comfortable text
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #4a4a5e; background-color: #1e1e2f; }
            QTabBar::tab { 
                background: #2f2f40; 
                color: #aaa; 
                padding: 12px 50px; 
                min-width: 150px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected { 
                background: #00d2ff; 
                color: #1e1e2f; 
            }
        """)
        
        self.tab_shells = QWidget()
        self.setup_shells_tab()
        self.tabs.addTab(self.tab_shells, "Reverse Shells & Listeners")
        
        self.tab_servers = QWidget()
        self.setup_servers_tab()
        self.tabs.addTab(self.tab_servers, "File Servers & C2")
        
        main_layout.addWidget(self.tabs)

    # --- TAB 1: SHELLS & LISTENERS ---
    def setup_shells_tab(self):
        layout = QHBoxLayout(self.tab_shells)
        
        # LEFT: Generator (Payloads)
        gen_group = QGroupBox("Payload Generator")
        gen_group.setStyleSheet("QGroupBox { font-weight: bold; color: #00d2ff; border: 1px solid #4a4a5e; margin-top: 10px; }")
        gen_layout = QVBoxLayout(gen_group)
        
        form = QFormLayout()
        self.combo_ip = QComboBox() 
        self.inp_port = QLineEdit("4444")
        self.combo_type = QComboBox() 
        
        self.combo_type.currentIndexChanged.connect(self.generate_payload)
        self.combo_ip.currentIndexChanged.connect(self.generate_payload)
        self.inp_port.textChanged.connect(self.generate_payload)
        
        form.addRow("LHOST (IP):", self.combo_ip)
        form.addRow("LPORT:", self.inp_port)
        form.addRow("Payload Type:", self.combo_type)
        gen_layout.addLayout(form)
        
        self.txt_payload = QTextEdit()
        self.txt_payload.setFixedHeight(120)
        self.txt_payload.setReadOnly(True)
        self.txt_payload.setStyleSheet("background-color: #101015; color: #00ff00; font-family: Consolas;")
        gen_layout.addWidget(QLabel("Generated One-Liner:"))
        gen_layout.addWidget(self.txt_payload)
        
        btn_refresh = QPushButton("Refresh IPs / DB"); btn_refresh.clicked.connect(self.refresh_and_reload)
        btn_manage = QPushButton("Manage Payloads (DB)"); btn_manage.clicked.connect(self.open_manager)
        
        gen_layout.addWidget(btn_refresh)
        gen_layout.addWidget(btn_manage)
        gen_layout.addStretch()
        
        # RIGHT: Listener Tabs (4 by default)
        right_layout = QVBoxLayout()
        self.listener_tabs = QTabWidget()
        self.listener_tabs.setStyleSheet("""
            QTabBar::tab { padding: 8px 20px; font-size: 12px; min-width: 80px; }
        """)
        
        # Create 4 listeners
        for i in range(1, 5):
            listener = NetcatListenerWidget(self.working_directory)
            self.listener_tabs.addTab(listener, f"Listener {i}")
            self.listeners.append(listener)
            
        right_layout.addWidget(self.listener_tabs)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(gen_group)
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([350, 550])
        layout.addWidget(splitter)

    # --- TAB 2: SERVERS ---
    def setup_servers_tab(self):
        layout = QVBoxLayout(self.tab_servers)
        
        # Header
        h_ctrl = QHBoxLayout()
        h_ctrl.addWidget(QLabel("Manage File Servers:", styleSheet="font-size:14px; font-weight:bold; color:#00d2ff;"))
        btn_manage = QPushButton("Manage Server DB")
        btn_manage.clicked.connect(self.open_manager)
        h_ctrl.addStretch()
        h_ctrl.addWidget(btn_manage)
        layout.addLayout(h_ctrl)
        
        # Server Tabs
        self.server_tabs = QTabWidget()
        self.server_tabs.setStyleSheet("""
            QTabBar::tab { padding: 8px 20px; font-size: 12px; min-width: 100px; }
        """)
        
        # Init 2 Servers
        for i in range(1, 3):
            srv = FileServerWidget(self.working_directory, self.db_path)
            self.server_tabs.addTab(srv, f"Server {i}")
            self.servers.append(srv)
            
        layout.addWidget(self.server_tabs)

    # --- Logic ---
    def open_manager(self):
        dlg = C2ManagerDialog(self.db_path, self)
        dlg.exec_()
        self.load_payload_options()
        for s in self.servers: s.load_options()

    def refresh_and_reload(self):
        self.refresh_ips()
        self.load_payload_options()

    def refresh_ips(self):
        self.combo_ip.clear()
        interfaces = QNetworkInterface.allInterfaces()
        for iface in interfaces:
            if iface.flags() & QNetworkInterface.IsUp and not (iface.flags() & QNetworkInterface.IsLoopBack):
                for entry in iface.addressEntries():
                    if entry.ip().protocol() == QAbstractSocket.IPv4Protocol:
                        ip = entry.ip().toString()
                        self.combo_ip.addItem(f"{iface.name()}: {ip}", ip)
        if self.combo_ip.count() == 0: self.combo_ip.addItem("127.0.0.1", "127.0.0.1")
        self.generate_payload()

    def load_payload_options(self):
        self.combo_type.clear()
        payloads = c2_db_manager.get_payloads(self.db_path)
        for p in payloads:
            self.combo_type.addItem(p['name'], p['template'])
        self.generate_payload()

    def generate_payload(self):
        ip = self.combo_ip.currentData()
        port = self.inp_port.text()
        tmpl = self.combo_type.currentData()
        if tmpl and ip and port:
            final = tmpl.replace("{IP}", ip).replace("{PORT}", port)
            self.txt_payload.setText(final)