import os
import re
import shlex
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QProgressBar, QInputDialog, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QProcess
from PyQt5.QtGui import QFont

from utils import db as command_db
from utils import project_db
from utils.worker import Worker
from modules.background_tasks import BackgroundTasksDialog

try:
    from modules.dialogs import CommandEditorDialog
except ImportError:
    CommandEditorDialog = None

class ScanControlWidget(QWidget):
    """
    Modernized Scan Control Tab.
    - Configuration (Target/Scope) is handled via Main Menu.
    - UI is focused strictly on Execution and Monitoring.
    """
    scan_updated = pyqtSignal()
    cwd_changed = pyqtSignal(str)
    theme_changed = pyqtSignal()
    background_task_started = pyqtSignal(int, str)
    active_task_count_changed = pyqtSignal(int)

    def __init__(self, working_directory, icon_path, project_db_path=None, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.icon_path = icon_path
        self.project_db_path = project_db_path
        self.worker = None
        self.current_font_size = 10
        
        # Internal state
        self.target_name = ""
        self.scope_file_path = None
        self.sudo_password = None

        # --- PROCESSES ---
        # 1. Naabu
        self.naabu_process = QProcess(self)
        self.naabu_process.readyReadStandardOutput.connect(self.handle_naabu_stdout)
        self.naabu_process.readyReadStandardError.connect(self.handle_naabu_stderr)
        self.naabu_process.finished.connect(self.handle_naabu_finished)

        # 2. Nmap (TCP)
        self.nmap_process = QProcess(self)
        self.nmap_process.readyReadStandardOutput.connect(self.handle_nmap_stdout)
        self.nmap_process.readyReadStandardError.connect(self.handle_nmap_stderr)
        self.nmap_process.finished.connect(self.handle_nmap_finished)

        # 3. Nmap (UDP)
        self.udp_process = QProcess(self)
        self.udp_process.readyReadStandardOutput.connect(self.handle_udp_stdout)
        self.udp_process.readyReadStandardError.connect(self.handle_udp_stderr)
        self.udp_process.finished.connect(self.handle_udp_finished)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ---------------------------------------------------------
        # 1. INFORMATION PANEL
        # ---------------------------------------------------------
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)
        label_style = "QLabel { background-color: #2b2b3b; border: 1px solid #4a4a5e; border-radius: 6px; padding: 10px; color: #ffffff; font-weight: bold; font-size: 13px; }"

        self.lbl_target = QLabel(f"TARGET: [Not Set]"); self.lbl_target.setStyleSheet(label_style)
        self.lbl_scope = QLabel(f"SCOPE: [Not Set]"); self.lbl_scope.setStyleSheet(label_style)
        self.lbl_cwd = QLabel(f"CWD: {self.working_directory}"); self.lbl_cwd.setStyleSheet(label_style)

        info_layout.addWidget(self.lbl_target); info_layout.addWidget(self.lbl_scope); info_layout.addWidget(self.lbl_cwd)
        main_layout.addLayout(info_layout)

        # ---------------------------------------------------------
        # 2. CONTROL TOOLBAR
        # ---------------------------------------------------------
        toolbar_layout = QHBoxLayout(); toolbar_layout.setSpacing(10)

        self.start_button = QPushButton("▶ START SCAN"); self.start_button.setFixedSize(140, 50)
        self.start_button.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #218838; }")
        self.start_button.clicked.connect(self.start_scan)
        
        self.stop_button = QPushButton("■ STOP SCAN"); self.stop_button.setEnabled(False); self.stop_button.setFixedSize(140, 50)
        self.stop_button.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; border-radius: 6px; } QPushButton:disabled { background-color: #5a3a3a; color: #888; }")
        self.stop_button.clicked.connect(self.stop_scan)

        self.naabu_button = QPushButton("⚡ NAABU (SUDO)"); self.naabu_button.setFixedSize(150, 50)
        self.naabu_button.setStyleSheet("QPushButton { background-color: #6f42c1; color: white; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #5a32a3; }")
        self.naabu_button.clicked.connect(self.run_naabu_scan)

        # NMAP TCP BUTTON (Initially Disabled)
        self.nmap_button = QPushButton("🔍 TCP SCAN"); self.nmap_button.setFixedSize(150, 50); self.nmap_button.setEnabled(False)
        self.nmap_button.setStyleSheet("QPushButton { background-color: #007bff; color: white; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #0056b3; } QPushButton:disabled { background-color: #2f3b4c; color: #666; border: 1px solid #444; }")
        self.nmap_button.clicked.connect(self.run_nmap_scan)

        # NMAP UDP BUTTON (Initially Disabled)
        self.udp_button = QPushButton("🎯 UDP SCAN"); self.udp_button.setFixedSize(150, 50); self.udp_button.setEnabled(False)
        self.udp_button.setStyleSheet("QPushButton { background-color: #fd7e14; color: white; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #e36a0d; } QPushButton:disabled { background-color: #2f3b4c; color: #666; border: 1px solid #444; }")
        self.udp_button.clicked.connect(self.run_udp_scan)

        zoom_style = "QPushButton { background-color: #4a4a5e; color: white; font-size: 18px; font-weight: bold; border-radius: 6px; }"
        btn_zoom_out = QPushButton("-"); btn_zoom_out.setFixedSize(50, 50); btn_zoom_out.setStyleSheet(zoom_style); btn_zoom_out.clicked.connect(lambda: self.zoom_log(-1))
        btn_zoom_in = QPushButton("+"); btn_zoom_in.setFixedSize(50, 50); btn_zoom_in.setStyleSheet(zoom_style); btn_zoom_in.clicked.connect(lambda: self.zoom_log(1))

        toolbar_layout.addWidget(self.start_button); toolbar_layout.addWidget(self.stop_button)
        toolbar_layout.addWidget(self.naabu_button); toolbar_layout.addWidget(self.nmap_button); toolbar_layout.addWidget(self.udp_button)
        toolbar_layout.addStretch(); toolbar_layout.addWidget(btn_zoom_out); toolbar_layout.addWidget(btn_zoom_in)
        main_layout.addLayout(toolbar_layout)

        # ---------------------------------------------------------
        # 2.5 COMMAND PREVIEWS
        # ---------------------------------------------------------
        # Helper for input styling
        input_style = "QLineEdit { background-color: #222; font-family: Consolas; border: 1px solid #444; padding: 4px; }"
        label_cmd_style = "color: #ccc; font-weight: bold;"

        # Naabu
        naabu_layout = QHBoxLayout()
        self.inp_naabu_cmd = QLineEdit(); self.inp_naabu_cmd.setStyleSheet(input_style + " color: #00ff00;")
        naabu_layout.addWidget(QLabel("Naabu Command:", styleSheet=label_cmd_style)); naabu_layout.addWidget(self.inp_naabu_cmd)
        main_layout.addLayout(naabu_layout)

        # Nmap TCP
        nmap_layout = QHBoxLayout()
        self.inp_nmap_cmd = QLineEdit(); self.inp_nmap_cmd.setStyleSheet(input_style + " color: #00ccff;")
        nmap_layout.addWidget(QLabel("TCP Command:  ", styleSheet=label_cmd_style)); nmap_layout.addWidget(self.inp_nmap_cmd)
        main_layout.addLayout(nmap_layout)

        # Nmap UDP
        udp_layout = QHBoxLayout()
        self.inp_udp_cmd = QLineEdit(); self.inp_udp_cmd.setStyleSheet(input_style + " color: #ffab40;")
        udp_layout.addWidget(QLabel("UDP Command:  ", styleSheet=label_cmd_style)); udp_layout.addWidget(self.inp_udp_cmd)
        main_layout.addLayout(udp_layout)

        # ---------------------------------------------------------
        # 3. LOGGING AREA
        # ---------------------------------------------------------
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False); self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #4a4a5e; border-radius: 4px; text-align: center; background-color: #1e1e2f; color: white; } QProgressBar::chunk { background-color: #007bff; }")
        self.timer_label = QLabel("00:00:00"); self.timer_label.setStyleSheet("font-family: monospace; font-size: 16px; font-weight: bold; color: #00d2ff;"); self.timer_label.setVisible(False)
        progress_layout.addWidget(self.progress_bar); progress_layout.addWidget(self.timer_label)
        main_layout.addLayout(progress_layout)
        
        self.scan_timer = QTimer(self); self.scan_timer.timeout.connect(self.update_timer_display); self.elapsed_time = 0
        self.output_log = QTextEdit(readOnly=True); self.output_log.setFont(QFont("Courier", self.current_font_size)); self.output_log.setStyleSheet("QTextEdit { border: 1px solid #4a4a5e; background-color: #15151b; color: #e0e0e0; border-radius: 6px; padding: 5px; }")
        main_layout.addWidget(self.output_log)

        self.bg_tasks_dialog = BackgroundTasksDialog(self)
        self.background_task_started.connect(self.bg_tasks_dialog.add_background_task)
        self.bg_tasks_dialog.task_termination_requested.connect(self.terminate_selected_bg_task)
        self.bg_monitor_timer = QTimer(self); self.bg_monitor_timer.timeout.connect(self.monitor_background_tasks); self.bg_monitor_timer.start(5000)

        # DATA LOADING
        if self.project_db_path:
            self.load_project_info()
            self.update_log(f"[*] Loaded project database: {os.path.basename(self.project_db_path)}")
        else:
            possible_scope = os.path.join(self.working_directory, "scope.txt")
            if os.path.exists(possible_scope):
                self.scope_file_path = possible_scope
                self.lbl_scope.setText(f"SCOPE: {os.path.basename(possible_scope)}")
                self.update_command_previews()
            self.update_log("[*] Manual Mode (No DB).")
            self.check_scan_availability() # Initial Check

    # --- Methods ---
    
    def check_scan_availability(self):
        """Checks if naabu_out exists. Enables/Disables Nmap TCP/UDP buttons."""
        naabu_out = os.path.join(self.working_directory, "naabu_out")
        ready = os.path.exists(naabu_out) and os.path.getsize(naabu_out) > 0
        
        # Enable TCP
        self.nmap_button.setEnabled(ready)
        self.nmap_button.setToolTip("Ready to scan found targets" if ready else "Run Naabu first to generate targets")
        
        # Enable UDP
        self.udp_button.setEnabled(True)
        self.udp_button.setToolTip("Ready to scan found targets" if ready else "Run Naabu first to generate targets")

    def update_command_previews(self):
        scope = self.scope_file_path if self.scope_file_path else "<SCOPE_FILE>"
        
        # Naabu
        naabu_out = os.path.join(self.working_directory, "naabu_out")
        self.inp_naabu_cmd.setText(f"naabu -list {scope} -o {naabu_out}")
        
        # Nmap TCP
        # Note: We use a sanitized file, but for preview we show 'naabu_out' to indicate dependency
        nmap_out = os.path.join(self.working_directory, "nmap_out")
        self.inp_nmap_cmd.setText(f"nmap -sC -sV -O -iL naabu_out -oN {nmap_out}")

        # Nmap UDP
        # Defaults to Top 100 ports for speed, using the same target list
        udp_out = os.path.join(self.working_directory, "nmap_udp_out")
        self.inp_udp_cmd.setText(f"nmap -sU --top-ports 100 -sV -iL {scope} -oN {udp_out}")

    def load_project_info(self):
        data = project_db.load_project_data(self.project_db_path)
        if data:
            self.target_name = data.get('client_name', '')
            self.lbl_target.setText(f"TARGET: {self.target_name}") 
            scope_path = os.path.join(self.working_directory, "scope.txt")
            if os.path.exists(scope_path):
                self.scope_file_path = scope_path
                self.lbl_scope.setText(f"SCOPE: {os.path.basename(scope_path)}") 
            else:
                self.scope_file_path = None
                self.update_log("[!] scope.txt not found in project folder.")
            
            self.update_command_previews()
            self.check_scan_availability()

    # ... [Helpers] ...
    def open_command_editor(self):
        if CommandEditorDialog: CommandEditorDialog(self).exec_()
    def show_background_tasks(self): self.bg_tasks_dialog.show()
    def toggle_theme(self): command_db.toggle_theme(); self.theme_changed.emit()
    def apply_theme(self, theme_name): pass 
    def zoom_log(self, direction):
        self.current_font_size += direction
        if self.current_font_size < 6: self.current_font_size = 6
        self.output_log.setFont(QFont("Courier", self.current_font_size))
    def ansi_to_html(self, text):
        color_map = {'30': 'black', '31': 'red', '32': 'green', '33': 'yellow', '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white', '90': 'grey', '91': 'lightcoral', '92': 'lightgreen', '93': 'lightyellow', '94': 'lightblue', '95': 'lightpink', '96': 'lightcyan'}
        def replace_color(match): return f'<span style="color:{color_map.get(match.group(1), "white")}">'
        html = re.sub(r'\x1b\[(\d+)m', replace_color, text)
        html = html.replace('\x1b[0m', '</span>')
        return html.replace('\n', '<br>')
    def update_progress_bar(self, current_step, total_steps): self.progress_bar.setValue(current_step); self.progress_bar.setFormat(f"Step {current_step}/{total_steps}")
    def update_timer_display(self):
        self.elapsed_time += 1
        hours, rem = divmod(self.elapsed_time, 3600); minutes, seconds = divmod(rem, 60)
        self.timer_label.setText(f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
    def prompt_for_sudo_password(self):
        if not self.sudo_password:
            text, ok = QInputDialog.getText(self, "Sudo Required", "Enter sudo password for scanning:", QLineEdit.Password)
            if ok and text: self.sudo_password = text; return True
            return False
        return True

    def _prepare_nmap_targets(self, source_file):
        """Helper to create a sanitized IP list from naabu output."""
        targets_file = os.path.join(self.working_directory, "nmap_targets.txt")
        try:
            unique_ips = set()
            with open(source_file, 'r') as f:
                for line in f:
                    if ":" in line:
                        ip = line.strip().split(":")[0] # Extract IP
                        unique_ips.add(ip)
                    elif line.strip():
                        unique_ips.add(line.strip())
            
            with open(targets_file, 'w') as f:
                f.write("\n".join(unique_ips))
            return targets_file
        except Exception as e:
            self.update_log(f"[!] Error preparing target list: {e}")
            return None

    # --- EXECUTION: NAABU ---
    def run_naabu_scan(self):
        cmd_str = self.inp_naabu_cmd.text().strip()
        if not cmd_str: QMessageBox.warning(self, "Empty Command", "Enter valid command."); return
        if self.naabu_process.state() == QProcess.Running: QMessageBox.warning(self, "Busy", "Scan running."); return
        if not self.prompt_for_sudo_password(): return

        if cmd_str.startswith("sudo "): cmd_str = cmd_str[5:].strip()
        cmd_args = shlex.split(cmd_str)
        
        exec_dir = self.working_directory
        if self.project_db_path:
            project_dir = os.path.dirname(self.project_db_path)
            if os.path.exists(project_dir): exec_dir = project_dir
        
        self.update_log(f"<br><span style='color: #6f42c1;'><b>[⚡] Starting Naabu Scan (Sudo)</b></span>")
        self.update_log(f"Command: sudo {cmd_str}")

        self.naabu_process.setWorkingDirectory(exec_dir)
        self.naabu_process.start("sudo", ["-S"] + cmd_args)
        
        if self.naabu_process.waitForStarted():
            self.naabu_process.write((self.sudo_password + "\n").encode())
            self.naabu_button.setEnabled(False); self.start_button.setEnabled(False); self.stop_button.setEnabled(True)
        else: self.update_log(f"[!] Failed to start Naabu: {self.naabu_process.errorString()}")

    def handle_naabu_stdout(self): self.update_log(self.naabu_process.readAllStandardOutput().data().decode(errors='ignore').strip())
    def handle_naabu_stderr(self):
        d = self.naabu_process.readAllStandardError().data().decode(errors='ignore').strip()
        if d and "[sudo]" not in d: self.update_log(f"<span style='color:orange;'>{d}</span>")
    def handle_naabu_finished(self):
        self.naabu_button.setEnabled(True); self.start_button.setEnabled(True); self.stop_button.setEnabled(False)
        self.update_log(f"<br><span style='color: #28a745;'><b>[✔] Naabu scan finished.</b></span>")
        if self.project_db_path:
            project_db.mark_step_complete(self.project_db_path, "Naabu Scan", True)
            
        self.check_scan_availability() 
        self.scan_updated.emit()

    # --- EXECUTION: NMAP (TCP) ---
    def run_nmap_scan(self):
        cmd_str = self.inp_nmap_cmd.text().strip()
        if not cmd_str: QMessageBox.warning(self, "Empty Command", "Enter valid command."); return
        if self.nmap_process.state() == QProcess.Running: QMessageBox.warning(self, "Busy", "Scan running."); return
        if not self.prompt_for_sudo_password(): return

        # Pre-flight: Check naabu_out
        naabu_out = os.path.join(self.working_directory, "naabu_out")
        if not os.path.exists(naabu_out):
            QMessageBox.critical(self, "Missing Dependency", "naabu_out file not found. Run Naabu first."); return

        # SANITIZATION: Create a temporary file with just IPs
        if "naabu_out" in cmd_str:
            targets_file = self._prepare_nmap_targets(naabu_out)
            if targets_file:
                cmd_str = cmd_str.replace("naabu_out", "nmap_targets.txt")
                self.update_log("[i] Created sanitized target list: nmap_targets.txt")

        if cmd_str.startswith("sudo "): cmd_str = cmd_str[5:].strip()
        cmd_args = shlex.split(cmd_str)
        
        exec_dir = self.working_directory
        if self.project_db_path:
            project_dir = os.path.dirname(self.project_db_path)
            if os.path.exists(project_dir): exec_dir = project_dir
        
        self.update_log(f"<br><span style='color: #00ccff;'><b>[🔍] Starting Nmap TCP Scan (Sudo)</b></span>")
        self.update_log(f"Command: sudo {cmd_str}")

        self.nmap_process.setWorkingDirectory(exec_dir)
        self.nmap_process.start("sudo", ["-S"] + cmd_args)
        
        if self.nmap_process.waitForStarted():
            self.nmap_process.write((self.sudo_password + "\n").encode())
            self.nmap_button.setEnabled(False); self.start_button.setEnabled(False); self.stop_button.setEnabled(True)
        else: self.update_log(f"[!] Failed to start Nmap: {self.nmap_process.errorString()}")

    def handle_nmap_stdout(self):
        data = self.nmap_process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if data: self.update_log(f"<span style='color:#aaddff;'>{data}</span>")
    def handle_nmap_stderr(self):
        d = self.nmap_process.readAllStandardError().data().decode(errors='ignore').strip()
        if d and "[sudo]" not in d: self.update_log(f"<span style='color:orange;'>{d}</span>")
    def handle_nmap_finished(self):
        self.nmap_button.setEnabled(True); self.start_button.setEnabled(True); self.stop_button.setEnabled(False)
        self.update_log(f"<br><span style='color: #28a745;'><b>[✔] Nmap TCP scan finished.</b></span>")
        if self.project_db_path:
            project_db.mark_step_complete(self.project_db_path, "Nmap TCP Scan", True)
        self.scan_updated.emit()

    def run_udp_scan(self):
        cmd_str = self.inp_udp_cmd.text().strip()
        if not cmd_str: QMessageBox.warning(self, "Empty Command", "Enter valid command."); return
        if self.udp_process.state() == QProcess.Running: QMessageBox.warning(self, "Busy", "Scan running."); return
        if not self.prompt_for_sudo_password(): return

        # REMOVED: Pre-flight check for naabu_out
        # REMOVED: Sanitization logic for naabu_out

        if cmd_str.startswith("sudo "): cmd_str = cmd_str[5:].strip()
        cmd_args = shlex.split(cmd_str)
        
        exec_dir = self.working_directory
        if self.project_db_path:
            project_dir = os.path.dirname(self.project_db_path)
            if os.path.exists(project_dir): exec_dir = project_dir
        
        self.update_log(f"<br><span style='color: #fd7e14;'><b>[🎯] Starting UDP Scan (Sudo)</b></span>")
        self.update_log(f"Command: sudo {cmd_str}")

        self.udp_process.setWorkingDirectory(exec_dir)
        self.udp_process.start("sudo", ["-S"] + cmd_args)
        
        if self.udp_process.waitForStarted():
            self.udp_process.write((self.sudo_password + "\n").encode())
            self.udp_button.setEnabled(False); self.start_button.setEnabled(False); self.stop_button.setEnabled(True)
        else: self.update_log(f"[!] Failed to start UDP Scan: {self.udp_process.errorString()}")

    def handle_udp_stdout(self):
        data = self.udp_process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if data: self.update_log(f"<span style='color:#ffcc80;'>{data}</span>")
    def handle_udp_stderr(self):
        d = self.udp_process.readAllStandardError().data().decode(errors='ignore').strip()
        if d and "[sudo]" not in d: self.update_log(f"<span style='color:orange;'>{d}</span>")
    def handle_udp_finished(self):
        self.udp_button.setEnabled(True); self.start_button.setEnabled(True); self.stop_button.setEnabled(False)
        self.update_log(f"<br><span style='color: #28a745;'><b>[✔] UDP scan finished.</b></span>")
        # Optional: Add project_db milestone for UDP if you wish
        if self.project_db_path:
            project_db.mark_step_complete(self.project_db_path, "Nmap UDP Scan", True)
        self.scan_updated.emit()
        self.scan_updated.emit()

    # ... [Generic Execution Methods] ...
    def start_scan(self):
        if not self.target_name: QMessageBox.warning(self, "Input Error", "Target Name not set."); return
        if not self.scope_file_path: QMessageBox.warning(self, "Input Error", "Scope File not found."); return
        self.output_log.clear(); self.start_button.setEnabled(False); self.stop_button.setEnabled(True)
        
        commands = command_db.get_all_commands(); total = len(commands)
        self.progress_bar.setMaximum(total); self.progress_bar.setValue(0); self.progress_bar.setVisible(True)
        self.elapsed_time = 0; self.timer_label.setVisible(True); self.scan_timer.start(1000)
        
        self.worker = Worker(target_name=self.target_name, scope_file=self.scope_file_path, working_directory=self.working_directory)
        self.worker.progress.connect(self.update_log); self.worker.progress_updated.connect(self.update_progress_bar)
        self.worker.scan_updated.connect(self.scan_updated); self.worker.background_task_started.connect(self.background_task_started)
        self.worker.finished.connect(self.scan_finished); self.worker.error.connect(self.show_error_message)
        self.worker.start()

    def stop_scan(self):
        if self.worker and self.worker.isRunning(): self.worker.stop()
        if self.naabu_process.state() == QProcess.Running: self.naabu_process.terminate(); self.update_log("[!] Terminating Naabu...")
        if self.nmap_process.state() == QProcess.Running: self.nmap_process.terminate(); self.update_log("[!] Terminating TCP Scan...")
        if self.udp_process.state() == QProcess.Running: self.udp_process.terminate(); self.update_log("[!] Terminating UDP Scan...")
        self.scan_timer.stop()

    def update_log(self, message): self.output_log.append(self.ansi_to_html(message))
    def scan_finished(self):
        self.scan_timer.stop()
        if self.worker and self.worker.is_running: self.progress_bar.setValue(self.progress_bar.maximum()); self.progress_bar.setFormat("Scan Completed")
        else: self.progress_bar.setFormat("Scan Cancelled")
        self.start_button.setEnabled(True); self.stop_button.setEnabled(False); self.worker = None

        # UPDATE DB PROGRESS
        if self.project_db_path:
            project_db.mark_step_complete(self.project_db_path, "Basic HTTP Check", True)

    def show_error_message(self, message): self.update_log(f"[!!!] ERROR: {message}"); QMessageBox.critical(self, "Error", message)
    def add_background_task(self, pid, command): self.bg_tasks_dialog.add_background_task(pid, command); self.update_bg_task_button_count()
    def terminate_selected_bg_task(self, pid):
        if self.worker and pid in self.worker.background_processes:
            try: self.worker.background_processes[pid].terminate(); self.update_log(f"[!] Terminated BG task {pid}.")
            except Exception as e: self.show_error_message(f"Kill failed: {e}")
        else: self.show_error_message(f"PID {pid} not active.")
    def monitor_background_tasks(self):
        if not self.worker or not self.worker.background_processes: self.update_bg_task_button_count(); return
        finished = []
        for pid, proc in list(self.worker.background_processes.items()):
            if proc.poll() is not None: finished.append(pid)
        for pid in finished:
            del self.worker.background_processes[pid]; self.bg_tasks_dialog.remove_background_task(pid); self.update_log(f"[✔] BG Task {pid} finished.")
        self.update_bg_task_button_count()
    def update_bg_task_button_count(self):
        c = len(self.worker.background_processes) if self.worker else 0; self.active_task_count_changed.emit(c)
    def on_cwd_changed(self, new_path): self.working_directory = new_path; self.lbl_cwd.setText(f"CWD: {self.working_directory}")