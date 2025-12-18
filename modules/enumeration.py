import sys
import re
import subprocess
import os
import html
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QRadioButton, QGroupBox, 
    QCheckBox, QLineEdit, QFormLayout, QTextEdit, 
    QProgressBar, QSplitter, QMessageBox, QScrollArea, QFileDialog, QFrame, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# Import DB Managers
from utils.enum_db_manager import EnumDBManager
from utils import project_db  # Import project_db to fetch credentials

# ---------------------------------------------------------
# 1. WORKER THREAD
# ---------------------------------------------------------
class EnumWorker(QThread):
    log_output = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, command_list, working_dir):
        super().__init__()
        self.command_list = command_list
        self.working_dir = working_dir
        self.is_running = True

    def run(self):
        total = len(self.command_list)
        for i, cmd in enumerate(self.command_list):
            if not self.is_running: break
            
            display_cmd = re.sub(r"echo '.*?' \| sudo -S", "echo '******' | sudo -S", cmd)
            
            self.progress_update.emit(i, total)
            self.log_output.emit(f"<br><b><span style='color: #00d2ff;'>[*] Executing ({i+1}/{total}): {display_cmd}</span></b><br>")
            
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
                    self.log_output.emit(line.strip())
                
                process.stdout.close()
                process.wait()
                
            except Exception as e:
                self.error.emit(f"Error executing command: {str(e)}")

        self.progress_update.emit(total, total)
        self.finished.emit()

    def stop(self):
        self.is_running = False
        self.log_output.emit("<br><span style='color: orange;'>[!] Stopping execution...</span>")

# ---------------------------------------------------------
# 2. MAIN WIDGET
# ---------------------------------------------------------
class EnumerationWidget(QWidget):
    def __init__(self, working_directory, project_db_path=None, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.project_db_path = project_db_path # Store the DB path
        self.db = EnumDBManager() 
        self.worker = None
        self.input_fields = {}

        self.init_ui()
        
        if self.db.is_empty():
            self.check_for_default_csv()
        
        self.load_services()

    def check_for_default_csv(self):
        default_csv = os.path.join("utils", "enumeration_commands.csv")
        if os.path.exists(default_csv):
            success, msg = self.db.import_from_csv(default_csv)
            if not success:
                print(f"Failed to auto-load CSV: {msg}")

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # --- PANE 1: SERVICES (Left) ---
        pane_services = QWidget()
        layout_services = QVBoxLayout(pane_services)
        layout_services.setContentsMargins(0,0,0,0)
        
        lbl_serv = QLabel("1. SELECT SERVICE")
        lbl_serv.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_serv.setStyleSheet("color: #00d2ff; margin-bottom: 5px;")
        
        self.list_services = QListWidget()
        self.list_services.setStyleSheet("""
            QListWidget {
                background-color: #1e1e2f;
                border: 1px solid #4a4a5e;
                border-radius: 8px;
            }
            QListWidget::item {
                height: 60px;
                color: #e0e0e0;
                font-size: 16px;
                font-weight: bold;
                padding-left: 15px;
                margin: 4px;
                background-color: #2f2f40;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #00d2ff;
                color: #15151b;
            }
            QListWidget::item:hover {
                border: 1px solid #00d2ff;
            }
        """)
        self.list_services.itemClicked.connect(self.on_service_selected)
        
        btn_import_csv = QPushButton("Import CSV")
        btn_import_csv.clicked.connect(self.import_csv_dialog)
        btn_import_csv.setStyleSheet("padding: 10px;")
        
        layout_services.addWidget(lbl_serv)
        layout_services.addWidget(self.list_services)
        layout_services.addWidget(btn_import_csv)

        # --- PANE 2: CONFIGURATION (Middle) ---
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

        lbl_conf = QLabel("2. CONFIGURE")
        lbl_conf.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_conf.setStyleSheet("color: #00d2ff;")
        self.layout_config.addWidget(lbl_conf)

        gb_mode = QGroupBox("Execution Mode")
        gb_mode.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: white; border: 1px solid #4a4a5e; margin-top: 5px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        vbox_mode = QVBoxLayout()
        self.rb_sequence = QRadioButton("Sequence Mode (Run All)")
        self.rb_single = QRadioButton("Single Mode (Pick One)")
        self.rb_sequence.setChecked(True)
        self.rb_sequence.setStyleSheet("font-size: 14px; padding: 5px;")
        self.rb_single.setStyleSheet("font-size: 14px; padding: 5px;")
        
        self.rb_sequence.toggled.connect(self.update_command_list_view)
        vbox_mode.addWidget(self.rb_sequence)
        vbox_mode.addWidget(self.rb_single)
        gb_mode.setLayout(vbox_mode)

        gb_opts = QGroupBox("Filters & Options")
        gb_opts.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: white; border: 1px solid #4a4a5e; margin-top: 5px; }")
        vbox_opts = QVBoxLayout()
        
        hbox_filters = QHBoxLayout()
        combo_style = "QComboBox { background-color: #222; color: #00d2ff; border: 1px solid #444; padding: 4px; border-radius: 4px; } QComboBox::drop-down { border: none; }"
        
        self.combo_auth = QComboBox()
        self.combo_auth.addItems(["All (Auth)", "Auth Required", "No Auth"])
        self.combo_auth.setStyleSheet(combo_style)
        self.combo_auth.currentIndexChanged.connect(self.update_command_list_view)
        
        self.combo_sudo = QComboBox()
        self.combo_sudo.addItems(["All (Sudo)", "Sudo Required", "No Sudo"])
        self.combo_sudo.setStyleSheet(combo_style)
        self.combo_sudo.currentIndexChanged.connect(self.update_command_list_view)
        
        hbox_filters.addWidget(QLabel("Auth:", styleSheet="color: #ccc;"))
        hbox_filters.addWidget(self.combo_auth)
        hbox_filters.addWidget(QLabel("Sudo:", styleSheet="color: #ccc;"))
        hbox_filters.addWidget(self.combo_sudo)
        
        hbox_pw = QHBoxLayout()
        lbl_pw = QLabel("Sudo Password:")
        lbl_pw.setStyleSheet("font-size: 14px; color: #ccc;")
        self.inp_root_pw = QLineEdit()
        self.inp_root_pw.setEchoMode(QLineEdit.Password)
        self.inp_root_pw.setPlaceholderText("Required if Sudo cmds present")
        self.inp_root_pw.setStyleSheet("padding: 5px; color: #00d2ff; background-color: #222; border: 1px solid #444;")
        self.inp_root_pw.textChanged.connect(self.update_preview_text)
        
        hbox_pw.addWidget(lbl_pw)
        hbox_pw.addWidget(self.inp_root_pw)
        
        vbox_opts.addLayout(hbox_filters)
        vbox_opts.addLayout(hbox_pw)
        gb_opts.setLayout(vbox_opts)

        # Command Queue
        self.list_commands = QListWidget()
        self.list_commands.setSelectionMode(QListWidget.SingleSelection)
        self.list_commands.setMinimumHeight(200)
        self.list_commands.setStyleSheet("""
            QListWidget {
                background-color: #1a1a25;
                border: 1px solid #4a4a5e;
                border-radius: 5px;
            }
            QListWidget::item {
                height: 50px;
                padding: 5px;
                color: #ddd;
                border-bottom: 1px solid #2a2a35;
            }
            QListWidget::item:selected {
                background-color: #007acc;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #2a2a35;
            }
        """)
        self.list_commands.itemClicked.connect(self.generate_variable_inputs)

        self.scroll_vars = QScrollArea()
        self.scroll_vars.setWidgetResizable(True)
        self.container_vars = QWidget()
        self.layout_vars = QFormLayout(self.container_vars)
        self.scroll_vars.setWidget(self.container_vars)
        self.scroll_vars.setFixedHeight(120)

        lbl_preview = QLabel("Command Preview (About to run):")
        lbl_preview.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaa;")
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFixedHeight(300) 
        self.txt_preview.setStyleSheet("""
            background-color: #101015; 
            color: #00ff00; 
            font-family: Consolas; 
            font-size: 13px;
            border: 1px solid #444;
        """)

        self.btn_execute = QPushButton("EXECUTE COMMANDS")
        self.btn_execute.setFixedHeight(50) 
        self.btn_execute.setStyleSheet("""
            QPushButton { background-color: #28a745; color: white; font-weight: bold; font-size: 16px; border-radius: 5px; }
            QPushButton:hover { background-color: #38b755; }
        """)
        self.btn_execute.clicked.connect(self.start_execution)

        self.layout_config.addWidget(gb_mode)
        self.layout_config.addWidget(gb_opts)
        self.layout_config.addWidget(QLabel("Command Queue:", styleSheet="font-size:14px; font-weight:bold;"))
        self.layout_config.addWidget(self.list_commands)
        self.layout_config.addWidget(QLabel("Variables:", styleSheet="font-size:14px; font-weight:bold;"))
        self.layout_config.addWidget(self.scroll_vars)
        self.layout_config.addWidget(lbl_preview)
        self.layout_config.addWidget(self.txt_preview)
        self.layout_config.addWidget(self.btn_execute)
        
        self.scroll_config.setWidget(self.config_content)
        layout_config_container.addWidget(self.scroll_config)

        # --- PANE 3: OUTPUT (Right) ---
        pane_output = QWidget()
        layout_output = QVBoxLayout(pane_output)
        layout_output.setContentsMargins(0,0,0,0)
        
        lbl_out = QLabel("3. OUTPUT")
        lbl_out.setFont(QFont("Arial", 12, QFont.Bold))
        lbl_out.setStyleSheet("color: #00d2ff;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("height: 20px;")
        
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setStyleSheet("background-color: #1e1e2f; color: #e0e0e0; font-family: Consolas; font-size: 13px;")
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_execution)
        self.btn_stop.setEnabled(False)

        layout_output.addWidget(lbl_out)
        layout_output.addWidget(self.progress_bar)
        layout_output.addWidget(self.text_output)
        layout_output.addWidget(self.btn_stop)

        splitter.addWidget(pane_services)
        splitter.addWidget(pane_config_container)
        splitter.addWidget(pane_output)
        splitter.setSizes([250, 450, 500])

        main_layout.addWidget(splitter)

    # ---------------------------------------------------------
    # LOGIC
    # ---------------------------------------------------------
    def import_csv_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if file_path:
            success, msg = self.db.import_from_csv(file_path)
            if success:
                QMessageBox.information(self, "Success", msg)
                self.load_services()
            else:
                QMessageBox.critical(self, "Error", msg)

    def load_services(self):
        self.list_services.clear()
        services = self.db.get_services()
        for s in services:
            self.list_services.addItem(s)

    def on_service_selected(self, item):
        self.update_command_list_view()

    def update_command_list_view(self):
        selected_items = self.list_services.selectedItems()
        if not selected_items: return
        
        service = selected_items[0].text()
        
        auth_idx = self.combo_auth.currentIndex()
        auth_map = {0: None, 1: 1, 2: 0}
        auth_val = auth_map.get(auth_idx)

        sudo_idx = self.combo_sudo.currentIndex()
        sudo_map = {0: None, 1: 1, 2: 0}
        sudo_val = sudo_map.get(sudo_idx)

        commands = self.db.get_commands(service, auth_filter=auth_val, sudo_filter=sudo_val)
        
        self.list_commands.clear()
        
        for cmd in commands:
            prefix = ""
            if cmd['auth']: prefix += "[AUTH] "
            if cmd['sudo']: prefix += "[SUDO] "
            
            title = f"{prefix}{cmd['title']}"
            snippet = cmd['command']
            if len(snippet) > 60: snippet = snippet[:60] + "..."
            display_text = f"{title}\n   > {snippet}"
            
            item = QListWidgetItem(display_text)
            item.setToolTip(cmd['command'])
            item.setData(Qt.UserRole, cmd)
            self.list_commands.addItem(item)

        self.generate_variable_inputs()

    def generate_variable_inputs(self):
        # Clear existing inputs
        while self.layout_vars.count():
            child = self.layout_vars.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        self.input_fields = {}
        raw_cmd_data = []

        if self.rb_single.isChecked():
            current_item = self.list_commands.currentItem()
            if current_item:
                raw_cmd_data.append(current_item.data(Qt.UserRole))
        else:
            for i in range(self.list_commands.count()):
                raw_cmd_data.append(self.list_commands.item(i).data(Qt.UserRole))

        needed_vars = set()
        for data in raw_cmd_data:
            text = data['command']
            matches = re.findall(r'\{([\w_-]+)\}', text)
            for m in matches: needed_vars.add(m)

        # --- AUTO-FILL LOGIC ---
        # 1. Fetch Project Data
        project_data = {}
        if self.project_db_path:
            project_data = project_db.load_project_data(self.project_db_path)
        
        creds = project_data.get('credentials', [])
        domains = project_data.get('domains', [])
        
        # Simple Logic: Use first available credential
        first_user = creds[0]['username'] if creds else ""
        first_pass = creds[0]['password'] if creds else ""
        first_domain = domains[0] if domains else ""

        for var in sorted(list(needed_vars)):
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"Value for {var}")
            line_edit.setStyleSheet("padding: 5px; font-size: 13px;")
            
            # --- Try to Auto-Fill ---
            var_lower = var.lower()
            if var_lower in ['username', 'user', 'login']:
                line_edit.setText(first_user)
            elif var_lower in ['password', 'pass', 'pwd']:
                line_edit.setText(first_pass)
                line_edit.setEchoMode(QLineEdit.Password) # Optional safety
            elif var_lower in ['domain', 'domain_name']:
                line_edit.setText(first_domain)
            
            line_edit.textChanged.connect(self.update_preview_text)
            
            lbl = QLabel(f"{var}:")
            lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
            
            self.layout_vars.addRow(lbl, line_edit)
            self.input_fields[var] = line_edit
        
        self.update_preview_text()

    def update_preview_text(self):
        commands, _ = self.prepare_commands_and_validate(show_errors=False, is_preview=True)
        
        if not commands:
            self.txt_preview.setText("-- No commands selected or queue empty --")
            return

        html_out = ""
        for i, cmd in enumerate(commands):
            safe_cmd = html.escape(cmd)
            if "sudo" in safe_cmd:
                safe_cmd = safe_cmd.replace("sudo", "<span style='color:#ff5555; font-weight:bold;'>sudo</span>")
            
            row_html = f"""
            <div style="background-color:#1e1e2f; margin-bottom:8px; padding:8px; border-left: 4px solid #00d2ff;">
                <span style="color:#888; font-weight:bold;">#{i+1}</span> 
                <span style="font-family:Consolas; color:#aaddff; font-size:14px;">{safe_cmd}</span>
            </div>
            """
            html_out += row_html
        
        self.txt_preview.setHtml(html_out)

    def prepare_commands_and_validate(self, show_errors=True, is_preview=False):
        cmd_data_list = []
        if self.rb_single.isChecked():
            item = self.list_commands.currentItem()
            if not item: return [], False
            cmd_data_list.append(item.data(Qt.UserRole))
        else:
            if self.list_commands.count() == 0: return [], False
            for i in range(self.list_commands.count()):
                cmd_data_list.append(self.list_commands.item(i).data(Qt.UserRole))

        final_commands = []
        missing_vars = []
        root_pw = self.inp_root_pw.text().strip()

        for data in cmd_data_list:
            processed_cmd = data['command']
            needs_sudo = data['sudo']
            
            if needs_sudo:
                if not root_pw:
                    if not is_preview:
                        if show_errors:
                            QMessageBox.warning(self, "Sudo Required", "Root Password Required.")
                        return [], False
                    else:
                        if not processed_cmd.strip().startswith("sudo"):
                            processed_cmd = f"sudo {processed_cmd}"
                else:
                    if processed_cmd.strip().startswith("sudo"):
                        processed_cmd = re.sub(r'^sudo\s+', '', processed_cmd)
                    
                    if is_preview:
                        processed_cmd = f"echo '******' | sudo -S {processed_cmd}"
                    else:
                        processed_cmd = f"echo '{root_pw}' | sudo -S {processed_cmd}"

            req_vars = re.findall(r'\{([\w_-]+)\}', processed_cmd)
            for var in req_vars:
                if var in self.input_fields:
                    val = self.input_fields[var].text().strip()
                    if not val: 
                        missing_vars.append(var)
                    else: 
                        processed_cmd = processed_cmd.replace(f"{{{var}}}", val)
            final_commands.append(processed_cmd)

        if missing_vars and not is_preview:
            if show_errors:
                QMessageBox.warning(self, "Missing Input", f"Please fill: {', '.join(set(missing_vars))}")
            return [], False
            
        return final_commands, True

    def start_execution(self):
        if self.worker and self.worker.isRunning(): return

        final_commands, is_valid = self.prepare_commands_and_validate(show_errors=True, is_preview=False)
        if not is_valid or not final_commands: return

        self.text_output.clear()
        self.btn_execute.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self.worker = EnumWorker(final_commands, self.working_directory)
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