import sys
import re
import subprocess
import os
import html
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QRadioButton, QGroupBox, 
    QCheckBox, QLineEdit, QFormLayout, QTextEdit, 
    QProgressBar, QSplitter, QMessageBox, QScrollArea, 
    QFileDialog, QFrame, QComboBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from utils.enum_db_manager import EnumDBManager
from utils import project_db

# ---------------------------------------------------------
# 1. WORKER THREAD
# ---------------------------------------------------------
class EnumWorker(QThread):
    log_output = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, command_list, working_dir, save_path=None):
        super().__init__()
        self.command_list = command_list
        self.working_dir = working_dir
        self.save_path = save_path
        self.is_running = True

    def _log_to_file(self, text):
        if not self.save_path: return
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if not clean_text: return
        try:
            with open(self.save_path, 'a', encoding='utf-8') as f:
                f.write(clean_text + '\n')
        except: pass

    def run(self):
        total = len(self.command_list)
        if self.save_path:
            self._log_to_file(f"\n--- Enumeration Session Started ---")

        for i, cmd in enumerate(self.command_list):
            if not self.is_running: break
            
            display_cmd = re.sub(r"echo '.*?' \| sudo -S", "echo '******' | sudo -S", cmd)
            self.progress_update.emit(i, total)
            
            header_html = f"<br><b><span style='color: #00d2ff;'>[*] Executing ({i+1}/{total}): {display_cmd}</span></b><br>"
            self.log_output.emit(header_html)
            self._log_to_file(f"[*] Executing ({i+1}/{total}): {display_cmd}")
            
            try:
                process = subprocess.Popen(
                    cmd, shell=True, cwd=self.working_dir,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )

                for line in iter(process.stdout.readline, ''):
                    if not self.is_running:
                        process.terminate()
                        break
                    line = line.strip()
                    self.log_output.emit(line)
                    self._log_to_file(line)
                
                process.stdout.close()
                process.wait()
                
            except Exception as e:
                err = f"Error executing command: {str(e)}"
                self.error.emit(err)
                self._log_to_file(f"[!] {err}")

        self.progress_update.emit(total, total)
        if self.save_path:
            self._log_to_file("--- Enumeration Session Finished ---\n")
        self.finished.emit()

    def stop(self):
        self.is_running = False
        self.log_output.emit("<br><span style='color: orange;'>[!] Stopping execution...</span>")
        self._log_to_file("[!] Stopping execution...")

# ---------------------------------------------------------
# 2. ENUMERATION WIDGET
# ---------------------------------------------------------
class EnumerationWidget(QWidget):
    def __init__(self, working_directory, project_db_path=None, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.project_db_path = project_db_path
        self.db = EnumDBManager() 
        self.worker = None
        
        self.input_fields = {} 
        self.list_targets = None 
        self.combo_creds = None 
        self.inp_user = None
        self.inp_pass = None
        self.chk_completed = None 

        self.init_ui()
        
        if self.db.is_empty():
            self.check_for_default_csv()
        
        self.load_services()

    def check_for_default_csv(self):
        default_csv = os.path.join("utils", "enumeration_commands.csv")
        if os.path.exists(default_csv):
            self.db.import_from_csv(default_csv)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # PANE 1: SERVICES
        pane_services = QWidget()
        layout_services = QVBoxLayout(pane_services)
        layout_services.setContentsMargins(0,0,0,0)
        
        lbl_serv = QLabel("1. SELECT SERVICE")
        lbl_serv.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_serv.setStyleSheet("color: #00d2ff; margin-bottom: 5px;")
        
        self.list_services = QListWidget()
        self.list_services.setStyleSheet("""
            QListWidget { background-color: #1e1e2f; border: 1px solid #4a4a5e; border-radius: 8px; }
            QListWidget::item { height: 50px; color: #e0e0e0; font-size: 15px; font-weight: bold; padding-left: 10px; margin: 2px; background-color: #2f2f40; border-radius: 6px; }
            QListWidget::item:selected { background-color: #00d2ff; color: #15151b; }
            QListWidget::item:hover { border: 1px solid #00d2ff; }
        """)
        self.list_services.itemClicked.connect(self.on_service_selected)
        
        btn_import_csv = QPushButton("Import CSV")
        btn_import_csv.clicked.connect(self.import_csv_dialog)
        
        layout_services.addWidget(lbl_serv)
        layout_services.addWidget(self.list_services)
        layout_services.addWidget(btn_import_csv)

        # PANE 2: CONFIGURATION
        pane_config_container = QWidget()
        layout_config_container = QVBoxLayout(pane_config_container)
        layout_config_container.setContentsMargins(0,0,0,0)

        self.scroll_config = QScrollArea()
        self.scroll_config.setWidgetResizable(True)
        self.scroll_config.setFrameShape(QFrame.NoFrame)
        self.scroll_config.setStyleSheet("background-color: transparent;")
        
        self.config_content = QWidget()
        self.layout_config = QVBoxLayout(self.config_content)
        self.layout_config.setContentsMargins(15, 0, 15, 0)
        self.layout_config.setSpacing(10)

        # Header
        hbox_conf_header = QHBoxLayout()
        lbl_conf = QLabel("2. CONFIGURE")
        lbl_conf.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_conf.setStyleSheet("color: #00d2ff;")
        self.btn_execute = QPushButton("START")
        self.btn_execute.setCursor(Qt.PointingHandCursor)
        self.btn_execute.setFixedSize(180, 40)
        self.btn_execute.setStyleSheet("""
            QPushButton { background-color: #28a745; color: white; font-weight: bold; font-size: 14px; border-radius: 5px; }
            QPushButton:hover { background-color: #38b755; }
        """)
        self.btn_execute.clicked.connect(self.start_execution)
        hbox_conf_header.addWidget(lbl_conf)
        hbox_conf_header.addStretch()
        hbox_conf_header.addWidget(self.btn_execute)
        self.layout_config.addLayout(hbox_conf_header)

        # Status Tracker
        gb_status = QGroupBox("Enumeration Status")
        gb_status.setStyleSheet("QGroupBox { font-weight: bold; color: #aaa; border: 1px solid #4a4a5e; margin-top: 5px; }")
        hbox_status = QHBoxLayout(gb_status)
        self.chk_completed = QCheckBox("Mark Service as Completed for Selected Targets")
        self.chk_completed.setStyleSheet("QCheckBox { font-size: 14px; color: #00ff00; font-weight: bold; spacing: 10px; }")
        self.chk_completed.toggled.connect(self.on_status_toggled)
        hbox_status.addWidget(self.chk_completed)
        self.layout_config.addWidget(gb_status)

        # Execution Mode (FIXED STYLING)
        gb_mode = QGroupBox("Execution Mode")
        gb_mode.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: white; border: 1px solid #4a4a5e; }")
        vbox_mode = QVBoxLayout()
        
        self.rb_sequence = QRadioButton("Sequence Mode (Run All)")
        self.rb_single = QRadioButton("Single Mode (Pick One)")
        
        # Explicitly style radio buttons to ensure visibility
        rb_style = """
            QRadioButton { color: #e0e0e0; font-size: 14px; padding: 5px; }
            QRadioButton::indicator { width: 15px; height: 15px; border-radius: 7px; border: 2px solid #555; }
            QRadioButton::indicator:checked { background-color: #00d2ff; border-color: #00d2ff; }
        """
        self.rb_sequence.setStyleSheet(rb_style)
        self.rb_single.setStyleSheet(rb_style)
        
        self.rb_sequence.setChecked(True)
        self.rb_sequence.toggled.connect(self.update_command_list_view)
        
        vbox_mode.addWidget(self.rb_sequence)
        vbox_mode.addWidget(self.rb_single)
        gb_mode.setLayout(vbox_mode)
        self.layout_config.addWidget(gb_mode)

        # Filters
        gb_opts = QGroupBox("Filters")
        gb_opts.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: white; border: 1px solid #4a4a5e; }")
        hbox_filters = QHBoxLayout(gb_opts)
        self.combo_auth = QComboBox(); self.combo_auth.addItems(["All (Auth)", "Auth Required", "No Auth"]); self.combo_auth.currentIndexChanged.connect(self.update_command_list_view)
        self.combo_sudo = QComboBox(); self.combo_sudo.addItems(["All (Sudo)", "Sudo Required", "No Sudo"]); self.combo_sudo.currentIndexChanged.connect(self.update_command_list_view)
        hbox_filters.addWidget(QLabel("Auth:")); hbox_filters.addWidget(self.combo_auth)
        hbox_filters.addWidget(QLabel("Sudo:")); hbox_filters.addWidget(self.combo_sudo)
        self.layout_config.addWidget(gb_opts)

        # Sudo Password
        hbox_pw = QHBoxLayout()
        self.inp_root_pw = QLineEdit(); self.inp_root_pw.setEchoMode(QLineEdit.Password); self.inp_root_pw.setPlaceholderText("Required if Sudo cmds present")
        self.inp_root_pw.textChanged.connect(self.update_preview_text)
        hbox_pw.addWidget(QLabel("Sudo Password:")); hbox_pw.addWidget(self.inp_root_pw)
        self.layout_config.addLayout(hbox_pw)

        # Command Queue
        self.layout_config.addWidget(QLabel("Command Queue:", styleSheet="font-size:14px; font-weight:bold; margin-top:10px;"))
        self.list_commands = QListWidget()
        self.list_commands.setSelectionMode(QListWidget.SingleSelection)
        self.list_commands.setMinimumHeight(150)
        self.list_commands.setStyleSheet("QListWidget { background-color: #1a1a25; border: 1px solid #4a4a5e; border-radius: 5px; } QListWidget::item { padding: 5px; color: #ddd; border-bottom: 1px solid #2a2a35; } QListWidget::item:selected { background-color: #007acc; color: white; }")
        self.list_commands.itemClicked.connect(self.generate_variable_inputs)
        self.layout_config.addWidget(self.list_commands)

        # Variables
        self.layout_config.addWidget(QLabel("Variables & Targets:", styleSheet="font-size:14px; font-weight:bold; margin-top:10px;"))
        self.scroll_vars = QScrollArea(); self.scroll_vars.setWidgetResizable(True)
        self.container_vars = QWidget(); self.layout_vars = QFormLayout(self.container_vars)
        self.scroll_vars.setWidget(self.container_vars); self.scroll_vars.setFixedHeight(220)
        self.layout_config.addWidget(self.scroll_vars)

        # Preview
        self.layout_config.addWidget(QLabel("Command Preview:", styleSheet="font-size: 14px; font-weight: bold; color: #aaa; margin-top:10px;"))
        self.txt_preview = QTextEdit(); self.txt_preview.setReadOnly(True); self.txt_preview.setFixedHeight(200)
        self.txt_preview.setStyleSheet("background-color: #101015; color: #00ff00; font-family: Consolas; font-size: 12px; border: 1px solid #444;")
        self.layout_config.addWidget(self.txt_preview)

        self.scroll_config.setWidget(self.config_content)
        layout_config_container.addWidget(self.scroll_config)

        # PANE 3: OUTPUT
        pane_output = QWidget(); layout_output = QVBoxLayout(pane_output); layout_output.setContentsMargins(0,0,0,0)
        hbox_out_header = QHBoxLayout(); hbox_out_header.addWidget(QLabel("3. OUTPUT", styleSheet="font-family:Arial; font-size:12pt; font-weight:bold; color:#00d2ff;")); hbox_out_header.addStretch(); self.chk_save_output = QCheckBox("Save Output"); hbox_out_header.addWidget(self.chk_save_output); self.inp_save_filename = QLineEdit("enum_results.txt"); self.inp_save_filename.setPlaceholderText("Filename"); self.inp_save_filename.setFixedWidth(150); hbox_out_header.addWidget(self.inp_save_filename)
        self.progress_bar = QProgressBar(); self.progress_bar.setStyleSheet("height: 10px;")
        self.text_output = QTextEdit(); self.text_output.setReadOnly(True); self.text_output.setStyleSheet("background-color: #1e1e2f; color: #e0e0e0; font-family: Consolas; font-size: 13px;")
        self.btn_stop = QPushButton("STOP"); self.btn_stop.setFixedHeight(40); self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;"); self.btn_stop.clicked.connect(self.stop_execution); self.btn_stop.setEnabled(False)
        layout_output.addLayout(hbox_out_header); layout_output.addWidget(self.progress_bar); layout_output.addWidget(self.text_output); layout_output.addWidget(self.btn_stop)

        splitter.addWidget(pane_services); splitter.addWidget(pane_config_container); splitter.addWidget(pane_output); splitter.setSizes([250, 500, 500])
        main_layout.addWidget(splitter)

    # ---------------------------------------------------------
    # LOGIC
    # ---------------------------------------------------------
    def import_csv_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if file_path:
            self.db.import_from_csv(file_path)
            self.load_services()

    def load_services(self):
        self.list_services.clear()
        services = self.db.get_services()
        
        found_services = []
        if self.project_db_path:
            found_services = project_db.get_unique_services(self.project_db_path)
        
        for s in services:
            display = f"★ {s}" if s in found_services else s
            self.list_services.addItem(display)

    def on_service_selected(self, item):
        self.update_command_list_view()
        self.chk_completed.blockSignals(True)
        self.chk_completed.setChecked(False)
        self.chk_completed.blockSignals(False)

    def update_command_list_view(self):
        item = self.list_services.currentItem()
        if not item: return
        
        service = item.text().replace("★ ", "")
        
        auth_idx = self.combo_auth.currentIndex()
        auth_val = {0: None, 1: 1, 2: 0}.get(auth_idx)
        
        sudo_idx = self.combo_sudo.currentIndex()
        sudo_val = {0: None, 1: 1, 2: 0}.get(sudo_idx)

        commands = self.db.get_commands(service, auth_filter=auth_val, sudo_filter=sudo_val)
        
        self.list_commands.clear()
        for cmd in commands:
            prefix = ""
            if cmd['auth']: prefix += "[AUTH] "
            if cmd['sudo']: prefix += "[SUDO] "
            
            snippet = cmd['command']
            if len(snippet) > 70: snippet = snippet[:70] + "..."
            
            w_item = QListWidgetItem(f"{prefix}{cmd['title']}\n   > {snippet}")
            w_item.setToolTip(cmd['command'])
            w_item.setData(Qt.UserRole, cmd)
            self.list_commands.addItem(w_item)

        self.generate_variable_inputs()

    def generate_variable_inputs(self):
        # Reset UI
        while self.layout_vars.count():
            child = self.layout_vars.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        self.input_fields = {}
        self.list_targets = None
        self.combo_creds = None
        self.inp_user = None
        self.inp_pass = None
        
        raw_cmd_data = []
        if self.rb_single.isChecked():
            curr = self.list_commands.currentItem()
            if curr: raw_cmd_data.append(curr.data(Qt.UserRole))
        else:
            for i in range(self.list_commands.count()):
                raw_cmd_data.append(self.list_commands.item(i).data(Qt.UserRole))

        needed_vars = set()
        for data in raw_cmd_data:
            matches = re.findall(r'\{([\w_-]+)\}', data['command'])
            for m in matches: needed_vars.add(m)

        # 1. Targets (Smart Filtering)
        target_vars = {'IP', 'Target', 'Domain', 'Domain_Name'}
        needed_lower = {v.lower() for v in needed_vars}
        is_target_needed = any(t.lower() in needed_lower for t in target_vars)
        
        if is_target_needed:
            self.list_targets = QListWidget()
            self.list_targets.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.list_targets.setFixedHeight(120)
            self.list_targets.setStyleSheet("background-color: #222; color: white;")
            self.list_targets.itemSelectionChanged.connect(self.on_targets_changed)

            # --- FILTERING LOGIC ---
            filtered_hosts = []
            service_name = ""
            
            # Try to get service name from UI selection
            if self.list_services.currentItem():
                service_name = self.list_services.currentItem().text().replace("★ ", "")
            
            # Query DB
            if self.project_db_path and service_name:
                filtered_hosts = project_db.get_hosts_for_service(self.project_db_path, service_name)

            # Decide source
            if filtered_hosts:
                # Case A: Service found in DB -> Show Filtered Scope
                lbl_text = f"Select Targets ({len(filtered_hosts)} hosts with {service_name}):"
                for host in filtered_hosts:
                    self.list_targets.addItem(host)
            else:
                # Case B: Service not in DB -> Show Full Scope (Fallback)
                lbl_text = "Select Targets (Full Scope - Service not mapped):"
                scope_path = os.path.join(self.working_directory, "scope.txt")
                if os.path.exists(scope_path):
                    with open(scope_path, 'r') as f:
                        for line in f:
                            if line.strip(): self.list_targets.addItem(line.strip())

            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("font-weight: bold; color: #00d2ff;")
            self.layout_vars.addRow(lbl)
            self.layout_vars.addRow(self.list_targets)

        # 2. Credentials (Unchanged)
        cred_vars = {'Username', 'Password', 'User', 'Pass'}
        is_cred_needed = any(c.lower() in needed_lower for c in cred_vars)
        
        if is_cred_needed:
            self.layout_vars.addRow(QLabel("Select Credential:", styleSheet="font-weight: bold; color: #00d2ff;"))
            self.combo_creds = QComboBox()
            self.combo_creds.addItem("Manual / None", None)
            self.combo_creds.currentIndexChanged.connect(self.on_cred_selected)
            self.layout_vars.addRow(self.combo_creds)
            
            self.inp_user = QLineEdit(); self.inp_user.setPlaceholderText("{Username}"); self.inp_user.textChanged.connect(self.update_preview_text)
            self.inp_pass = QLineEdit(); self.inp_pass.setPlaceholderText("{Password}"); self.inp_pass.setEchoMode(QLineEdit.Password); self.inp_pass.textChanged.connect(self.update_preview_text)
            self.layout_vars.addRow("Username:", self.inp_user)
            self.layout_vars.addRow("Password:", self.inp_pass)
            
            self.filter_credentials_by_target([])

        # 3. Generic (Unchanged)
        handled = {'ip', 'target', 'domain', 'domain_name', 'username', 'password', 'user', 'pass'}
        for var in sorted(list(needed_vars)):
            if var.lower() in handled: continue
            le = QLineEdit()
            le.setPlaceholderText(f"Value for {var}")
            le.textChanged.connect(self.update_preview_text)
            self.layout_vars.addRow(QLabel(f"{var}:", styleSheet="font-weight:bold;"), le)
            self.input_fields[var] = le
        
        self.update_preview_text()
    def on_targets_changed(self):
        selected_ips = []
        if self.list_targets:
            selected_ips = [i.text() for i in self.list_targets.selectedItems()]
        
        if self.combo_creds:
            self.filter_credentials_by_target(selected_ips)
        
        self.update_status_checkbox(selected_ips)
        self.update_preview_text()

    def filter_credentials_by_target(self, selected_ips):
        if not self.project_db_path: return
        self.combo_creds.blockSignals(True)
        self.combo_creds.clear()
        self.combo_creds.addItem("Manual / None", None)
        
        all_creds = project_db.get_credentials(self.project_db_path)
        filtered = []
        for c in all_creds:
            host = c.get('host', '').strip()
            if not host: filtered.append(c)
            elif host in selected_ips: filtered.append(c)
        
        for c in filtered:
            display = f"{c['username']} @ {c.get('host','*')} ({c.get('service','')})"
            self.combo_creds.addItem(display, c)
        self.combo_creds.blockSignals(False)

    def on_cred_selected(self):
        data = self.combo_creds.currentData()
        if data:
            self.inp_user.setText(data['username'])
            self.inp_pass.setText(data['password'])
        self.update_preview_text()

    def update_status_checkbox(self, selected_ips):
        if not self.project_db_path or not self.list_services.currentItem(): return
        service = self.list_services.currentItem().text().replace("★ ", "")
        
        if not selected_ips:
            self.chk_completed.setChecked(False); return

        all_done = True
        for ip in selected_ips:
            if not project_db.get_enum_status(self.project_db_path, ip, service):
                all_done = False; break
        
        self.chk_completed.blockSignals(True)
        self.chk_completed.setChecked(all_done)
        self.chk_completed.blockSignals(False)

    def on_status_toggled(self, checked):
        if not self.project_db_path or not self.list_targets: return
        service = self.list_services.currentItem().text().replace("★ ", "")
        selected_ips = [i.text() for i in self.list_targets.selectedItems()]
        
        if not selected_ips:
            self.chk_completed.setChecked(False); return

        if checked:
            # CHECK IF THREAT MODELING WAS DONE (Record Exists)
            missing_hosts = []
            for ip in selected_ips:
                if not project_db.enum_record_exists(self.project_db_path, ip, service):
                    missing_hosts.append(ip)
            
            if missing_hosts:
                msg = f"Cannot mark as completed for {len(missing_hosts)} target(s):\n{', '.join(missing_hosts)}\n\nThreat Modeling has not populated these services yet. Please run Threat Modeling first."
                QMessageBox.warning(self, "Missing Enumeration Data", msg)
                self.chk_completed.blockSignals(True)
                self.chk_completed.setChecked(False)
                self.chk_completed.blockSignals(False)
                return

        for ip in selected_ips:
            project_db.set_enum_status(self.project_db_path, ip, service, checked)

    def update_preview_text(self):
        commands, _ = self.prepare_commands(show_errors=False, is_preview=True)
        if not commands:
            self.txt_preview.setText("-- No commands selected or targets missing --")
            return
        
        html_out = ""
        for i, cmd in enumerate(commands):
            safe = html.escape(cmd)
            if "sudo" in safe: safe = safe.replace("sudo", "<span style='color:#ff5555;font-weight:bold;'>sudo</span>")
            html_out += f"<div style='margin-bottom:5px; border-left:3px solid #00d2ff; padding-left:5px;'><b>#{i+1}</b> <span style='font-family:Consolas; color:#aaddff;'>{safe}</span></div>"
        self.txt_preview.setHtml(html_out)

    def prepare_commands(self, show_errors=True, is_preview=False):
        cmd_data = []
        if self.rb_single.isChecked():
            item = self.list_commands.currentItem()
            if not item: return [], False
            cmd_data.append(item.data(Qt.UserRole))
        else:
            for i in range(self.list_commands.count()):
                cmd_data.append(self.list_commands.item(i).data(Qt.UserRole))

        targets = []
        if self.list_targets:
            items = self.list_targets.selectedItems()
            targets = [i.text() for i in items]
            if not targets:
                if is_preview: targets = ["{TARGET}"]
                elif show_errors:
                    QMessageBox.warning(self, "No Target", "Select at least one target."); return [], False
        else:
            targets = [""]

        final_cmds = []
        missing_vars = []
        root_pw = self.inp_root_pw.text().strip()

        for target in targets:
            for data in cmd_data:
                cmd = data['command']
                
                if data['sudo']:
                    if not root_pw and not is_preview:
                        if show_errors: QMessageBox.warning(self, "Sudo", "Root Password Required."); return [], False
                    
                    if cmd.strip().startswith("sudo"): cmd = re.sub(r'^sudo\s+', '', cmd)
                    
                    if is_preview: cmd = f"echo '******' | sudo -S {cmd}"
                    else: cmd = f"echo '{root_pw}' | sudo -S {cmd}"

                reqs = re.findall(r'\{([\w_-]+)\}', cmd)
                for var in reqs:
                    vlow = var.lower()
                    val = None
                    
                    if vlow in ['ip', 'target', 'domain', 'domain_name']: val = target
                    elif vlow in ['user', 'username'] and self.inp_user: val = self.inp_user.text()
                    elif vlow in ['pass', 'password'] and self.inp_pass: val = self.inp_pass.text()
                    elif var in self.input_fields: val = self.input_fields[var].text().strip()
                    
                    if val: cmd = cmd.replace(f"{{{var}}}", val)
                    elif not is_preview: missing_vars.append(var)

                final_cmds.append(cmd)

        if missing_vars:
            if show_errors: QMessageBox.warning(self, "Missing Input", f"Please fill: {', '.join(set(missing_vars))}")
            return [], False

        return final_cmds, True

    def start_execution(self):
        if self.worker and self.worker.isRunning(): return
        
        cmds, ok = self.prepare_commands(show_errors=True)
        if not ok or not cmds: return

        save_path = None
        if self.chk_save_output.isChecked():
            fname = self.inp_save_filename.text().strip()
            if not fname: QMessageBox.warning(self, "Error", "Enter output filename."); return
            save_path = os.path.join(self.working_directory, fname)

        self.text_output.clear()
        self.btn_execute.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self.worker = EnumWorker(cmds, self.working_directory, save_path)
        self.worker.log_output.connect(self.text_output.append)
        self.worker.progress_update.connect(lambda c, t: self.progress_bar.setValue(int((c/t)*100)) if t > 0 else 0)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(lambda e: self.text_output.append(f"ERROR: {e}"))
        self.worker.start()

    def stop_execution(self):
        if self.worker: self.worker.stop()

    def on_finished(self):
        self.text_output.append("<br><b>[+] Done.</b>")
        self.btn_execute.setEnabled(True)
        self.btn_stop.setEnabled(False)
