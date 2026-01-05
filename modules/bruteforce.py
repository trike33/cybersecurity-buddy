import sys
import os
import signal
import subprocess
import time
import psutil 
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QSplitter, 
    QFrame, QGridLayout, QFileDialog, QDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor

from utils import bruteforce_db_manager

# ---------------------------------------------------------
# 1. PROCESS WORKER (Reusable)
# ---------------------------------------------------------
class BruteforceWorker(QThread):
    log_output = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, command, working_dir):
        super().__init__()
        self.command = command
        self.working_dir = working_dir
        self.process = None
        self.is_running = True
        self.start_time = None

    def run(self):
        self.start_time = time.time()
        try:
            self.process = subprocess.Popen(
                self.command, 
                shell=True, 
                cwd=self.working_dir,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid 
            )
            
            for line in iter(self.process.stdout.readline, ''):
                if not self.is_running: break
                self.log_output.emit(line.strip())
            
            self.process.stdout.close()
            self.process.wait()
        except Exception as e:
            self.log_output.emit(f"[!] Error: {str(e)}")
        finally:
            self.finished.emit()

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except: pass

# ---------------------------------------------------------
# 2. TERMINAL WIDGET (T1 / T2)
# ---------------------------------------------------------
class TerminalUnit(QWidget):
    status_changed = pyqtSignal(str, float) 

    def __init__(self, name, working_directory, parent=None):
        super().__init__(parent)
        self.name = name
        self.working_directory = working_directory
        self.worker = None
        self.start_timestamp = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.emit_runtime)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        gb = QGroupBox(f"{self.name} Configuration")
        gb.setStyleSheet("""
    QGroupBox {
        font-weight: bold;
        font-size: 16px;        /* 1. Larger text size */
        color: #00d2ff;
        border: 1px solid #444;
        margin-top: 20px;       /* 2. Create space at the top for the title */
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px;        /* 3. Add breathing room around the text */
        left: 10px;             /* 4. Indent the title slightly */
    }
""")
        gb_layout = QVBoxLayout(gb)
        
        row_cmd = QHBoxLayout()
        
        # Enforce label size so it doesn't get squashed
        lbl_cmd = QLabel("Command:")
        lbl_cmd.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        lbl_cmd.setStyleSheet("font-weight: bold; color: #ccc;")
        
        self.inp_cmd = QLineEdit()
        self.inp_cmd.setPlaceholderText(f"{self.name} Command...")
        self.inp_cmd.setStyleSheet("background-color: #222; color: #00ff00; font-family: Consolas; border: 1px solid #555;")
        
        self.btn_run = QPushButton("RUN")
        self.btn_run.setFixedWidth(80)
        self.btn_run.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.toggle_process)
        
        row_cmd.addWidget(lbl_cmd)
        row_cmd.addWidget(self.inp_cmd)
        row_cmd.addWidget(self.btn_run)
        gb_layout.addLayout(row_cmd)
        
        self.txt_out = QTextEdit()
        self.txt_out.setReadOnly(True)
        self.txt_out.setStyleSheet("background-color: #101015; color: #ccc; font-family: Consolas; font-size: 12px; border: none;")
        
        layout.addWidget(gb)
        layout.addWidget(self.txt_out)

    def set_command(self, cmd):
        self.inp_cmd.setText(cmd)

    def toggle_process(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker = None
            self.btn_run.setText("RUN")
            self.btn_run.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
            self.txt_out.append("\n[!] Process Stopped.")
            self.timer.stop()
            self.status_changed.emit("Stopped", 0)
        else:
            cmd = self.inp_cmd.text().strip()
            if not cmd: return
            
            self.txt_out.clear()
            self.txt_out.append(f"[*] Starting: {cmd}\n")
            
            self.worker = BruteforceWorker(cmd, self.working_directory)
            self.worker.log_output.connect(self.txt_out.append)
            self.worker.finished.connect(self.on_finished)
            self.worker.start()
            
            self.start_timestamp = time.time()
            self.timer.start(1000)
            
            self.btn_run.setText("STOP")
            self.btn_run.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
            self.status_changed.emit("Running", 0)

    def on_finished(self):
        self.btn_run.setText("RUN")
        self.btn_run.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.txt_out.append("\n[+] Finished.")
        self.timer.stop()
        self.status_changed.emit("Finished", time.time() - self.start_timestamp)

    def emit_runtime(self):
        if self.worker and self.worker.isRunning():
            elapsed = time.time() - self.start_timestamp
            self.status_changed.emit("Running", elapsed)

# ---------------------------------------------------------
# 3. STATS WIDGET (Right Pane)
# ---------------------------------------------------------
class StatsPane(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #1e1e2f; border-left: 2px solid #4a4a5e;")
        self.setMinimumWidth(250) # Use minimum instead of fixed to allow expansion
        
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        
        self.gb_t1 = self.create_stat_group("Terminal 1 Stats")
        self.lbl_t1_status = QLabel("Status: Idle")
        self.lbl_t1_time = QLabel("Runtime: 00:00:00")
        self.gb_t1.layout().addWidget(self.lbl_t1_status)
        self.gb_t1.layout().addWidget(self.lbl_t1_time)
        
        self.gb_t2 = self.create_stat_group("Terminal 2 Stats")
        self.lbl_t2_status = QLabel("Status: Idle")
        self.lbl_t2_time = QLabel("Runtime: 00:00:00")
        self.gb_t2.layout().addWidget(self.lbl_t2_status)
        self.gb_t2.layout().addWidget(self.lbl_t2_time)
        
        self.gb_net = self.create_stat_group("Network Traffic")
        self.lbl_sent = QLabel("Sent: 0 KB/s")
        self.lbl_recv = QLabel("Recv: 0 KB/s")
        self.lbl_sent.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 14px;")
        self.lbl_recv.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 14px;")
        self.gb_net.layout().addWidget(self.lbl_sent)
        self.gb_net.layout().addWidget(self.lbl_recv)
        
        self.layout.addWidget(self.gb_t1)
        self.layout.addWidget(self.gb_t2)
        self.layout.addWidget(self.gb_net)
        self.layout.addStretch()
        
        self.last_net_io = psutil.net_io_counters()
        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.update_network_stats)
        self.net_timer.start(1000)

    def create_stat_group(self, title):
        gb = QGroupBox(title)
        gb.setStyleSheet("QGroupBox { font-weight: bold; color: #aaa; border: 1px solid #444; margin-top: 10px; }")
        layout = QVBoxLayout(gb)
        return gb

    def update_t1(self, status, seconds):
        self.lbl_t1_status.setText(f"Status: {status}")
        self.lbl_t1_status.setStyleSheet(f"color: {'#00ff00' if status=='Running' else '#aaa'};")
        m, s = divmod(int(seconds), 60); h, m = divmod(m, 60)
        self.lbl_t1_time.setText(f"Runtime: {h:02}:{m:02}:{s:02}")

    def update_t2(self, status, seconds):
        self.lbl_t2_status.setText(f"Status: {status}")
        self.lbl_t2_status.setStyleSheet(f"color: {'#00ff00' if status=='Running' else '#aaa'};")
        m, s = divmod(int(seconds), 60); h, m = divmod(m, 60)
        self.lbl_t2_time.setText(f"Runtime: {h:02}:{m:02}:{s:02}")

    def update_network_stats(self):
        curr_io = psutil.net_io_counters()
        sent_bytes = curr_io.bytes_sent - self.last_net_io.bytes_sent
        recv_bytes = curr_io.bytes_recv - self.last_net_io.bytes_recv
        self.lbl_sent.setText(f"Sent: {sent_bytes / 1024:.1f} KB/s")
        self.lbl_recv.setText(f"Recv: {recv_bytes / 1024:.1f} KB/s")
        self.last_net_io = curr_io

# ---------------------------------------------------------
# 4. MANAGER DIALOG
# ---------------------------------------------------------
class BruteForceCommandManagerDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Manage Brute Force Commands")
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QTableWidget { background-color: #2f2f40; gridline-color: #4a4a5e; color: #e0e0e0; border: 1px solid #4a4a5e; }
            QHeaderView::section { background-color: #3e3e50; color: white; padding: 4px; }
            QLineEdit, QComboBox { background-color: #222; color: #00ff00; border: 1px solid #555; padding: 6px; }
            QPushButton { background-color: #3e3e50; color: white; padding: 8px; border: 1px solid #555; }
            QPushButton:hover { background-color: #4e4e60; border-color: #00d2ff; }
            QGroupBox { border: 1px solid #4a4a5e; margin-top: 10px; font-weight: bold; color: #aaa; }
        """)
        
        layout = QVBoxLayout(self)
        
        # --- Add New Section ---
        gb_add = QGroupBox("Add New Command / Import")
        lay_add = QVBoxLayout(gb_add)
        
        # Row 1: Manual Add
        h_manual = QHBoxLayout()
        self.inp_service = QComboBox()
        self.inp_service.setEditable(True)
        self.inp_service.setPlaceholderText("Service (e.g. SSH)")
        self.inp_tool = QLineEdit()
        self.inp_tool.setPlaceholderText("Tool (e.g. Hydra)")
        self.inp_tmpl = QLineEdit()
        self.inp_tmpl.setPlaceholderText("Template (e.g. hydra -l {USER} ...)")
        
        btn_add = QPushButton("Add Command")
        btn_add.clicked.connect(self.add_command)
        btn_add.setStyleSheet("background-color: #28a745; color: white;")
        
        h_manual.addWidget(self.inp_service, 1)
        h_manual.addWidget(self.inp_tool, 1)
        h_manual.addWidget(self.inp_tmpl, 3)
        h_manual.addWidget(btn_add)
        
        # Row 2: CSV Import
        h_csv = QHBoxLayout()
        btn_import = QPushButton("Import from CSV")
        btn_import.clicked.connect(self.import_csv)
        btn_import.setStyleSheet("background-color: #007bff; color: white;")
        lbl_hint = QLabel("CSV Format: service, tool, template")
        lbl_hint.setStyleSheet("color: #888; font-style: italic;")
        
        h_csv.addWidget(btn_import)
        h_csv.addWidget(lbl_hint)
        h_csv.addStretch()
        
        lay_add.addLayout(h_manual)
        lay_add.addLayout(h_csv)
        layout.addWidget(gb_add)
        
        # --- List Section ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Service", "Tool", "Template"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        # --- Footer ---
        h_foot = QHBoxLayout()
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self.delete_command)
        btn_del.setStyleSheet("background-color: #dc3545; color: white;")
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        
        h_foot.addWidget(btn_del)
        h_foot.addStretch()
        h_foot.addWidget(btn_close)
        layout.addLayout(h_foot)
        
        self.load_services_combo()
        self.load_table()

    def load_services_combo(self):
        self.inp_service.clear()
        services = bruteforce_db_manager.get_services(self.db_path)
        for _, name in services:
            self.inp_service.addItem(name)

    def load_table(self):
        self.table.setRowCount(0)
        data = bruteforce_db_manager.get_all_commands_detailed(self.db_path)
        for i, row in enumerate(data):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(row['service']))
            self.table.setItem(i, 2, QTableWidgetItem(row['tool_name']))
            self.table.setItem(i, 3, QTableWidgetItem(row['template']))

    def add_command(self):
        svc = self.inp_service.currentText().strip()
        tool = self.inp_tool.text().strip()
        tmpl = self.inp_tmpl.text().strip()
        
        if not svc or not tool or not tmpl:
            QMessageBox.warning(self, "Missing Input", "All fields are required.")
            return
            
        success, msg = bruteforce_db_manager.add_command(self.db_path, svc, tool, tmpl)
        if success:
            self.load_table()
            self.load_services_combo()
            self.inp_tool.clear()
            self.inp_tmpl.clear()
        else:
            QMessageBox.critical(self, "Error", msg)

    def delete_command(self):
        row = self.table.currentRow()
        if row >= 0:
            cid = self.table.item(row, 0).text()
            bruteforce_db_manager.delete_command(self.db_path, cid)
            self.load_table()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if path:
            success, msg = bruteforce_db_manager.import_from_csv(self.db_path, path)
            if success:
                QMessageBox.information(self, "Success", msg)
                self.load_table()
                self.load_services_combo()
            else:
                QMessageBox.critical(self, "Import Failed", msg)

# ---------------------------------------------------------
# 5. MAIN WIDGET
# ---------------------------------------------------------
class BruteForceWidget(QWidget):
    def __init__(self, working_directory, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resources_dir = os.path.join(base_dir, "resources")
        if not os.path.exists(resources_dir): os.makedirs(resources_dir)
        self.db_path = bruteforce_db_manager.initialize_bruteforce_db(resources_dir)
        
        self.init_ui()
        self.load_services()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # LEFT PANE
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setSpacing(10)
        
        # 1. Top Bar
        top_bar = QHBoxLayout()
        lbl_svc = QLabel("Target Service:")
        lbl_svc.setStyleSheet("font-weight:bold; font-size:14px; color:#00d2ff;")
        lbl_svc.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        self.combo_service = QComboBox()
        self.combo_service.currentIndexChanged.connect(self.on_service_changed)
        
        btn_manage = QPushButton("Manage DB")
        btn_manage.clicked.connect(self.open_manager)
        btn_manage.setFixedWidth(120)
        
        top_bar.addWidget(lbl_svc)
        top_bar.addWidget(self.combo_service)
        top_bar.addWidget(btn_manage)
        left_layout.addLayout(top_bar)
        
        # 2. Config Grid (Fixes layout issue)
        args_group = QGroupBox("Target Configuration")
        args_group.setStyleSheet("QGroupBox { font-weight: bold; color: #aaa; border: 1px solid #444; margin-top: 5px; }")
        
        args_grid = QGridLayout(args_group)
        args_grid.setContentsMargins(10, 15, 10, 10)
        args_grid.setSpacing(10)
        
        # Inputs
        self.inp_target = QLineEdit()
        self.inp_target.setPlaceholderText("e.g. 192.168.1.10")
        self.inp_target.textChanged.connect(self.update_previews)
        
        self.inp_user = QLineEdit()
        self.inp_user.setPlaceholderText("e.g. admin")
        self.inp_user.textChanged.connect(self.update_previews)
        
        self.inp_pass_file = QLineEdit()
        self.inp_pass_file.setPlaceholderText("/usr/share/wordlists/rockyou.txt")
        self.inp_pass_file.textChanged.connect(self.update_previews)
        
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self.browse_wordlist)
        
        # Grid Placement: Labels Top, Inputs Bottom
        args_grid.addWidget(QLabel("Target IP/Domain:"), 0, 0)
        args_grid.addWidget(self.inp_target, 1, 0)
        
        args_grid.addWidget(QLabel("Username:"), 0, 1)
        args_grid.addWidget(self.inp_user, 1, 1)
        
        args_grid.addWidget(QLabel("Wordlist Path:"), 0, 2)
        wl_layout = QHBoxLayout()
        wl_layout.addWidget(self.inp_pass_file)
        wl_layout.addWidget(btn_browse)
        args_grid.addLayout(wl_layout, 1, 2)
        
        left_layout.addWidget(args_group)
        
        # 3. Split Terminals
        splitter_v = QSplitter(Qt.Vertical)
        self.term1 = TerminalUnit("Terminal 1", self.working_directory)
        self.term2 = TerminalUnit("Terminal 2", self.working_directory)
        splitter_v.addWidget(self.term1)
        splitter_v.addWidget(self.term2)
        left_layout.addWidget(splitter_v)
        
        # RIGHT PANE
        self.stats_pane = StatsPane()
        self.term1.status_changed.connect(self.stats_pane.update_t1)
        self.term2.status_changed.connect(self.stats_pane.update_t2)
        
        main_layout.addWidget(left_pane, stretch=3)
        main_layout.addWidget(self.stats_pane, stretch=1)

    def load_services(self):
        current_id = self.combo_service.currentData()
        self.combo_service.blockSignals(True)
        self.combo_service.clear()
        services = bruteforce_db_manager.get_services(self.db_path)
        for s_id, name in services:
            self.combo_service.addItem(name, s_id)
        if current_id:
            idx = self.combo_service.findData(current_id)
            if idx >= 0: self.combo_service.setCurrentIndex(idx)
        self.combo_service.blockSignals(False)
        if self.combo_service.count() > 0 and not current_id:
            self.on_service_changed()

    def open_manager(self):
        dlg = BruteForceCommandManagerDialog(self.db_path, self)
        dlg.exec_()
        self.load_services() 
        self.update_previews()

    def browse_wordlist(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Wordlist", self.working_directory)
        if path: self.inp_pass_file.setText(path)

    def on_service_changed(self):
        self.update_previews()

    def update_previews(self):
        svc_id = self.combo_service.currentData()
        if not svc_id: return
        
        cmds = bruteforce_db_manager.get_commands_for_service(self.db_path, svc_id)
        
        target = self.inp_target.text() or "{TARGET}"
        user = self.inp_user.text() or "{USER}"
        pass_file = self.inp_pass_file.text() or "{PASS_FILE}"
        
        # Populate T1
        if len(cmds) > 0:
            tmpl = cmds[0]['template']
            final = tmpl.replace("{TARGET}", target).replace("{USER}", user).replace("{PASS_FILE}", pass_file)
            self.term1.set_command(final)
        else:
            self.term1.set_command("")
            
        # Populate T2
        if len(cmds) > 1:
            tmpl = cmds[1]['template']
            final = tmpl.replace("{TARGET}", target).replace("{USER}", user).replace("{PASS_FILE}", pass_file)
            self.term2.set_command(final)
        else:
            self.term2.set_command("")