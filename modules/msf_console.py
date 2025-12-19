import sys
import os
import re
import pty
import subprocess
import select
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QListWidget, QLabel, QSplitter, QGroupBox, QFrame,
    QPushButton, QGridLayout, QComboBox, QScrollArea,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QCursor

# ---------------------------------------------------------
# 1. PTY BACKEND (Unchanged)
# ---------------------------------------------------------
class PtyDriver(QThread):
    output_ready = pyqtSignal(str)
    process_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.master_fd = None
        self.process = None
        self.running = False

    def run(self):
        self.master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        cmd = ["msfconsole", "-n", "--no-readline"]
        
        try:
            self.process = subprocess.Popen(
                cmd, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                env=env, close_fds=True, preexec_fn=os.setsid
            )
            os.close(slave_fd)
            self.running = True
        except FileNotFoundError:
            self.output_ready.emit("[!] Error: 'msfconsole' not found in PATH.\n")
            return

        while self.running and self.process.poll() is None:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if self.master_fd in r:
                    data = os.read(self.master_fd, 10240)
                    if not data: break
                    text = data.decode('utf-8', errors='replace')
                    self.output_ready.emit(text)
            except OSError: break
        
        self.process_finished.emit()

    def write(self, data: str):
        if self.master_fd:
            try: os.write(self.master_fd, data.encode('utf-8'))
            except OSError: pass

    def stop(self):
        self.running = False
        if self.process: self.process.terminate()

# ---------------------------------------------------------
# 2. TERMINAL VIEW (Renderer)
# ---------------------------------------------------------
from PyQt5.QtWidgets import QTextEdit

class AnsiTerminal(QTextEdit):
    def __init__(self, pty_driver):
        super().__init__()
        self.pty = pty_driver
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #101015; color: #d4d4d4;
                border: 1px solid #4a4a5e;
                font-family: 'Consolas', 'Monospace'; font-size: 11pt;
            }
        """)

    def append_ansi(self, text):
        ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        text = re.sub(ip_pattern, r'<span style="color: #00d2ff; font-weight: bold;">\g<0></span>', text)
        cve_pattern = r"CVE-\d{4}-\d{4,7}"
        text = re.sub(cve_pattern, r'<span style="color: #ff5555; text-decoration: underline;">\g<0></span>', text)

        colors = {
            '\x1b[31m': 'color:#ff5555', '\x1b[32m': 'color:#50fa7b',
            '\x1b[34m': 'color:#bd93f9', '\x1b[33m': 'color:#f1fa8c',
            '\x1b[1m': 'font-weight:bold', '\x1b[4m': 'text-decoration:underline',
            '\x1b[0m': 'color:#d4d4d4; font-weight:normal; text-decoration:none'
        }
        
        formatted = text
        for code, style in colors.items():
            formatted = formatted.replace(code, f'</span><span style="{style}">')
        formatted = re.sub(r'\x1b\[[0-9;]*m', '', formatted)
        
        self.moveCursor(self.textCursor().End)
        self.insertHtml(f"<pre style='margin:0'><span>{formatted}</span></pre>")
        self.ensureCursorVisible()

# ---------------------------------------------------------
# 3. CONTROL PANEL (The "Brain")
# ---------------------------------------------------------
class MSFControlPanel(QFrame):
    """The Right Pane: Buttons and Helpers so you don't have to type commands."""
    command_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame { background-color: #1e1e2f; border-left: 1px solid #4a4a5e; }
            QLabel { color: #e0e0e0; font-weight: bold; }
            QPushButton { 
                background-color: #2f2f40; color: white; border: 1px solid #4a4a5e; 
                padding: 8px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3e3e50; border-color: #00d2ff; color: #00d2ff; }
            QPushButton:pressed { background-color: #00d2ff; color: #15151b; }
            QLineEdit, QComboBox { background-color: #252535; color: white; border: 1px solid #444; padding: 5px; }
            QGroupBox { margin-top: 15px; font-weight: bold; color: #aaa; border: 1px solid #444; border-radius: 5px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)

        # 1. Active Module Info
        self.lbl_module = QLabel("No Module Selected")
        self.lbl_module.setStyleSheet("font-size: 13px; color: #ff9900; margin-bottom: 5px;")
        self.lbl_module.setWordWrap(True)
        self.lbl_module.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.lbl_module)

        # 2. Module Actions (Grid)
        gb_actions = QGroupBox("Module Actions")
        gl_actions = QGridLayout(gb_actions)
        gl_actions.setSpacing(8)
        
        btn_opts = QPushButton("Options"); btn_opts.clicked.connect(lambda: self.send("show options"))
        btn_targ = QPushButton("Targets"); btn_targ.clicked.connect(lambda: self.send("show targets"))
        btn_payl = QPushButton("Payloads"); btn_payl.clicked.connect(lambda: self.send("show payloads"))
        btn_info = QPushButton("Info"); btn_info.clicked.connect(lambda: self.send("info"))
        btn_back = QPushButton("Back"); btn_back.clicked.connect(lambda: self.send("back"))
        btn_adv = QPushButton("Advanced"); btn_adv.clicked.connect(lambda: self.send("show advanced"))

        gl_actions.addWidget(btn_opts, 0, 0); gl_actions.addWidget(btn_targ, 0, 1)
        gl_actions.addWidget(btn_payl, 1, 0); gl_actions.addWidget(btn_info, 1, 1)
        gl_actions.addWidget(btn_adv, 2, 0); gl_actions.addWidget(btn_back, 2, 1)
        self.layout.addWidget(gb_actions)

        # 3. Execution (Big Buttons)
        gb_exec = QGroupBox("Execution")
        v_exec = QVBoxLayout(gb_exec)
        
        self.btn_check = QPushButton("Check Vulnerability")
        self.btn_check.clicked.connect(lambda: self.send("check"))
        self.btn_check.setStyleSheet("border-color: #ffaa00; color: #ffaa00;")
        
        self.btn_run = QPushButton("RUN / EXPLOIT")
        self.btn_run.clicked.connect(lambda: self.send("exploit"))
        self.btn_run.setFixedHeight(40)
        self.btn_run.setStyleSheet("background-color: #28a745; color: white; font-size: 14px;")
        
        self.btn_bg = QPushButton("Exploit in Background (-j)")
        self.btn_bg.clicked.connect(lambda: self.send("exploit -j"))
        
        v_exec.addWidget(self.btn_check)
        v_exec.addWidget(self.btn_run)
        v_exec.addWidget(self.btn_bg)
        self.layout.addWidget(gb_exec)

        # 4. Search Assistant
        gb_search = QGroupBox("Search Database")
        v_search = QVBoxLayout(gb_search)
        
        h_filter = QHBoxLayout()
        self.combo_type = QComboBox()
        self.combo_type.addItems(["All", "exploit", "auxiliary", "payload", "post"])
        h_filter.addWidget(QLabel("Type:"))
        h_filter.addWidget(self.combo_type)
        v_search.addLayout(h_filter)
        
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("e.g. smb, apache, cve-2024...")
        self.inp_search.returnPressed.connect(self.perform_search)
        
        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self.perform_search)
        btn_search.setStyleSheet("background-color: #007bff;")
        
        v_search.addWidget(self.inp_search)
        v_search.addWidget(btn_search)
        self.layout.addWidget(gb_search)

        # 5. Global Utils
        gb_utils = QGroupBox("Global Utils")
        h_utils = QHBoxLayout(gb_utils)
        btn_jobs = QPushButton("Jobs"); btn_jobs.clicked.connect(lambda: self.send("jobs -l"))
        btn_sess = QPushButton("Sessions"); btn_sess.clicked.connect(lambda: self.send("sessions -l"))
        h_utils.addWidget(btn_jobs)
        h_utils.addWidget(btn_sess)
        self.layout.addWidget(gb_utils)

        self.layout.addStretch()

    def send(self, cmd):
        self.command_requested.emit(cmd)

    def perform_search(self):
        term = self.inp_search.text().strip()
        if not term: return
        
        type_filter = self.combo_type.currentText()
        query = f"search {term}"
        if type_filter != "All":
            query = f"search type:{type_filter} {term}"
            
        self.send(query)

    def set_active_module(self, name):
        if not name:
            self.lbl_module.setText("No Module Selected")
            self.lbl_module.setStyleSheet("font-size: 13px; color: #888; margin-bottom: 5px;")
            self.btn_run.setEnabled(False)
            self.btn_check.setEnabled(False)
        else:
            self.lbl_module.setText(name)
            self.lbl_module.setStyleSheet("font-size: 13px; color: #00d2ff; font-weight: bold; margin-bottom: 5px;")
            self.btn_run.setEnabled(True)
            self.btn_check.setEnabled(True)

# ---------------------------------------------------------
# 4. MAIN EXPLOIT WIDGET
# ---------------------------------------------------------
class ExploitFrameworkWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.start_engine()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # --- LEFT PANE: SESSIONS ---
        left_widget = QWidget()
        l_layout = QVBoxLayout(left_widget)
        l_layout.setContentsMargins(0,0,0,0)
        
        l_group = QGroupBox("Active Sessions")
        l_group.setStyleSheet("QGroupBox { font-weight: bold; color: #00ff00; border: 1px solid #4a4a5e; margin-top: 10px; }")
        lg_layout = QVBoxLayout(l_group)
        self.list_sessions = QListWidget()
        self.list_sessions.setStyleSheet("background-color: #1e1e2f; color: #00ff00; border: none;")
        lg_layout.addWidget(self.list_sessions)
        l_layout.addWidget(l_group)
        
        # --- CENTER PANE: CONSOLE ---
        center_widget = QWidget()
        c_layout = QVBoxLayout(center_widget)
        c_layout.setContentsMargins(0,0,0,0)
        
        self.console_group = QGroupBox("Metasploit Console (msf6)")
        self.console_group.setStyleSheet("QGroupBox { font-weight: bold; color: #aaa; border: 1px solid #4a4a5e; margin-top: 10px; }")
        cg_layout = QVBoxLayout(self.console_group)
        
        self.terminal = AnsiTerminal(None) # PTY linked later
        cg_layout.addWidget(self.terminal)
        
        self.inp_cmd = QLineEdit()
        self.inp_cmd.setPlaceholderText("Enter command (e.g. 'use exploit/windows/smb/ms17_010_eternalblue')")
        self.inp_cmd.setStyleSheet("QLineEdit { background-color: #252535; color: #00d2ff; font-family: Consolas; border: 1px solid #4a4a5e; padding: 8px; font-weight: bold; }")
        self.inp_cmd.returnPressed.connect(self.send_user_command)
        cg_layout.addWidget(self.inp_cmd)
        c_layout.addWidget(self.console_group)
        
        # --- RIGHT PANE: CONTROL PANEL (NEW) ---
        self.controls = MSFControlPanel()
        self.controls.command_requested.connect(self.inject_command)
        
        # Assemble
        splitter.addWidget(left_widget)
        splitter.addWidget(center_widget)
        splitter.addWidget(self.controls)
        splitter.setSizes([200, 600, 300])
        
        main_layout.addWidget(splitter)

    def start_engine(self):
        self.pty = PtyDriver()
        self.pty.output_ready.connect(self.on_data_received)
        self.terminal.pty = self.pty # Link
        self.pty.start()

    def send_user_command(self):
        cmd = self.inp_cmd.text()
        if not cmd: return
        self.inject_command(cmd)
        self.inp_cmd.clear()

    def inject_command(self, cmd):
        """Sends a command to the PTY, echoes it locally, and handles heuristic updates."""
        if not self.pty: return
        
        # Heuristics: Update UI instantly if 'use' or 'back' is sent
        if cmd.strip().startswith("use "):
            mod = cmd.split(" ")[1]
            self.controls.set_active_module(mod)
        elif cmd.strip() == "back":
            self.controls.set_active_module(None)
            
        self.pty.write(cmd + "\n")

    def on_data_received(self, text):
        self.terminal.append_ansi(text)
        
        # 1. Detect Prompt Change (Active Module)
        # matches "msf6 exploit(windows/smb/...) >"
        match_mod = re.search(r"msf6 \w+\((.*?)\) >", text)
        if match_mod:
            current_mod = match_mod.group(1)
            self.controls.set_active_module(current_mod)
        elif "msf6 >" in text:
            self.controls.set_active_module(None)
            
        # 2. Detect Sessions
        if "session" in text and "opened" in text:
            clean = re.sub(r'\x1b\[[0-9;]*m', '', text).strip()
            self.list_sessions.addItem(clean)

    def closeEvent(self, event):
        if self.pty: self.pty.stop()
        event.accept()