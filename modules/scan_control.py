import os
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QProgressBar, QInputDialog
)
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont

from utils import db as command_db
from utils import project_db
from utils.worker import Worker
from modules.dialogs import DomainsFileDialog, CommandEditorDialog
from modules.background_tasks import BackgroundTasksDialog

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

        # --- Load Info from Project DB if available ---
        if self.project_db_path:
            self.load_project_info()

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ---------------------------------------------------------
        # 1. INFORMATION PANEL (Labels)
        # ---------------------------------------------------------
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)

        label_style = """
            QLabel {
                background-color: #2b2b3b;
                border: 1px solid #4a4a5e;
                border-radius: 6px;
                padding: 10px;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
        """

        self.lbl_target = QLabel(f"TARGET: {self.target_name if self.target_name else '[Not Set]'}")
        self.lbl_target.setStyleSheet(label_style)
        
        scope_text = "[Not Set]"
        if self.scope_file_path: 
            scope_text = os.path.basename(self.scope_file_path)
        elif self.project_db_path: 
            scope_text = "Database Scope"
            
        self.lbl_scope = QLabel(f"SCOPE: {scope_text}")
        self.lbl_scope.setStyleSheet(label_style)
        
        self.lbl_cwd = QLabel(f"CWD: {self.working_directory}")
        self.lbl_cwd.setStyleSheet(label_style)

        info_layout.addWidget(self.lbl_target)
        info_layout.addWidget(self.lbl_scope)
        info_layout.addWidget(self.lbl_cwd)
        
        main_layout.addLayout(info_layout)

        # ---------------------------------------------------------
        # 2. CONTROL TOOLBAR (Colorized)
        # ---------------------------------------------------------
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        # Start Button (Green/Teal)
        self.start_button = QPushButton("▶ START SCAN")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setFixedSize(180, 50)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745; 
                color: white; 
                font-weight: bold; font-size: 14px;
                border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #4a5a4a; color: #888; }
        """)
        self.start_button.clicked.connect(self.start_scan)
        
        # Stop Button (Red)
        self.stop_button = QPushButton("■ STOP SCAN")
        self.stop_button.setEnabled(False)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setFixedSize(180, 50)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545; 
                color: white; 
                font-weight: bold; font-size: 14px;
                border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #c82333; }
            QPushButton:disabled { background-color: #5a3a3a; color: #888; }
        """)
        self.stop_button.clicked.connect(self.stop_scan)

        # Zoom Buttons (Neutral/Blue)
        zoom_style = """
            QPushButton {
                background-color: #4a4a5e; color: white;
                font-size: 18px; font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #5a5a6e; }
        """
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(50, 50)
        btn_zoom_out.setStyleSheet(zoom_style)
        btn_zoom_out.clicked.connect(lambda: self.zoom_log(-1))

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(50, 50)
        btn_zoom_in.setStyleSheet(zoom_style)
        btn_zoom_in.clicked.connect(lambda: self.zoom_log(1))

        # Add to Layout
        toolbar_layout.addWidget(self.start_button)
        toolbar_layout.addWidget(self.stop_button)
        toolbar_layout.addStretch() 
        toolbar_layout.addWidget(btn_zoom_out)
        toolbar_layout.addWidget(btn_zoom_in)

        main_layout.addLayout(toolbar_layout)

        # ---------------------------------------------------------
        # 3. PROGRESS BAR & TIMER
        # ---------------------------------------------------------
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                text-align: center;
                background-color: #1e1e2f;
                color: white;
            }
            QProgressBar::chunk { background-color: #007bff; }
        """)
        
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet("font-family: monospace; font-size: 16px; font-weight: bold; color: #00d2ff;")
        self.timer_label.setVisible(False)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.timer_label)
        main_layout.addLayout(progress_layout)
        
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.update_timer_display)
        self.elapsed_time = 0
        
        # ---------------------------------------------------------
        # 4. LOGGING AREA
        # ---------------------------------------------------------
        self.output_log = QTextEdit(readOnly=True)
        self.output_log.setFont(QFont("Courier", self.current_font_size))
        self.output_log.setStyleSheet("""
            QTextEdit {
                border: 1px solid #4a4a5e;
                background-color: #15151b;
                color: #e0e0e0;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        main_layout.addWidget(self.output_log)

        # Background Tasks Logic (Invisible)
        self.bg_tasks_dialog = BackgroundTasksDialog(self)
        self.background_task_started.connect(self.bg_tasks_dialog.add_background_task)
        self.bg_tasks_dialog.task_termination_requested.connect(self.terminate_selected_bg_task)
        self.bg_monitor_timer = QTimer(self)
        self.bg_monitor_timer.timeout.connect(self.monitor_background_tasks)
        self.bg_monitor_timer.start(5000)

        # Initial Log Message
        self.update_log("[*] System Ready.")
        if self.project_db_path:
            self.update_log(f"[*] Loaded project database: {os.path.basename(self.project_db_path)}")
        else:
            self.update_log("[*] Please configure Target, Scope, and CWD from the 'Tools' menu.")

    # --- Configuration Methods (Triggered by Main Menu) ---
    
    def load_project_info(self):
        """Loads Target and Scope from the attached DB."""
        data = project_db.load_project_data(self.project_db_path)
        if data:
            self.target_name = data.get('client_name', '')
            
            # Create a temporary scope file from DB domains
            domains = data.get('domains', [])
            if domains:
                scope_path = os.path.join(self.working_directory, "scope.txt")
                try:
                    with open(scope_path, "w") as f:
                        f.write("\n".join(domains))
                    self.scope_file_path = scope_path
                except Exception as e:
                    self.update_log(f"[!] Error writing scope file: {e}")

    def open_command_editor(self):
        dialog = CommandEditorDialog(self)
        dialog.exec_()

    def show_background_tasks(self):
        self.bg_tasks_dialog.setStyleSheet(self.window().styleSheet())
        self.bg_tasks_dialog.show()

    # --- Internal UI Logic ---

    def toggle_theme(self):
        command_db.toggle_theme()
        self.theme_changed.emit()

    def apply_theme(self, theme_name):
        pass 

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

    def update_progress_bar(self, current_step, total_steps):
        self.progress_bar.setValue(current_step)
        self.progress_bar.setFormat(f"Step {current_step}/{total_steps}")

    def update_timer_display(self):
        self.elapsed_time += 1
        hours, rem = divmod(self.elapsed_time, 3600)
        minutes, seconds = divmod(rem, 60)
        self.timer_label.setText(f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")

    # --- Execution Logic ---

    def start_scan(self):
        if not self.target_name:
            QMessageBox.warning(self, "Input Error", "Target Name is not set. Please set it via Tools > Set Target Name.")
            return
        if not self.scope_file_path:
            QMessageBox.warning(self, "Input Error", "Scope File is not selected. Please set it via Tools > Browse Scope File.")
            return

        self.output_log.clear()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        commands = command_db.get_all_commands()
        total_commands = len(commands)
        
        self.progress_bar.setMaximum(total_commands)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Step 0/{total_commands}")
        self.progress_bar.setVisible(True)
        
        self.elapsed_time = 0
        self.timer_label.setText("00:00:00")
        self.timer_label.setVisible(True)
        self.scan_timer.start(1000)
        
        self.worker = Worker(target_name=self.target_name, scope_file=self.scope_file_path, working_directory=self.working_directory)
        self.worker.progress.connect(self.update_log)
        self.worker.progress_updated.connect(self.update_progress_bar)
        self.worker.scan_updated.connect(self.scan_updated)
        self.worker.background_task_started.connect(self.background_task_started)
        self.worker.finished.connect(self.scan_finished)
        self.worker.error.connect(self.show_error_message)
        self.worker.start()

    def stop_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        self.scan_timer.stop()

    def update_log(self, message):
        html_message = self.ansi_to_html(message)
        self.output_log.append(html_message)

    def scan_finished(self):
        self.scan_timer.stop()
        if self.worker and self.worker.is_running:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.progress_bar.setFormat("Scan Completed")
        else:
            self.progress_bar.setFormat("Scan Cancelled")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.worker = None

    def show_error_message(self, message):
        self.update_log(f"[!!!] ERROR: {message}")
        QMessageBox.critical(self, "Error", message)

    def add_background_task(self, pid, command):
        self.bg_tasks_dialog.add_background_task(pid, command)
        self.update_bg_task_button_count()

    def terminate_selected_bg_task(self, pid):
        if self.worker and pid in self.worker.background_processes:
            try:
                self.worker.background_processes[pid].terminate()
                self.update_log(f"[!] Manually terminated background task [PID: {pid}].")
            except Exception as e:
                self.show_error_message(f"Could not terminate process {pid}: {e}")
        else:
            self.show_error_message(f"Could not find active process with PID {pid}.")

    def monitor_background_tasks(self):
        if not self.worker or not self.worker.background_processes:
            self.update_bg_task_button_count()
            return
        finished_pids = []
        for pid, proc in list(self.worker.background_processes.items()):
            if proc.poll() is not None:
                finished_pids.append(pid)
        for pid in finished_pids:
            if pid in self.worker.background_processes:
                del self.worker.background_processes[pid]
            self.bg_tasks_dialog.remove_background_task(pid)
            self.update_log(f"[✔] Background task [PID: {pid}] finished.")
        self.update_bg_task_button_count()
    
    def update_bg_task_button_count(self):
        count = 0
        if self.worker and self.worker.background_processes:
            count = len(self.worker.background_processes)
        self.active_task_count_changed.emit(count)
        
    def on_cwd_changed(self, new_path):
        self.working_directory = new_path
        self.lbl_cwd.setText(f"CWD: {self.working_directory}")