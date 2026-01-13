import os
import re
import html
import sys
import shutil
import difflib
from urllib.parse import urlparse
from collections import Counter
import webbrowser
import subprocess

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDialog,
    QTableView, QHeaderView, QMessageBox, QPushButton, QHBoxLayout,
    QTextEdit, QDialogButtonBox, QTabWidget, QListWidget, QLabel, QMenu,
    QStyleOption, QStyle, QLineEdit, QCheckBox, QApplication, QFrame,
    QFileSystemModel, QAction, QToolButton, QAbstractItemView, QGroupBox,
    QMainWindow, QSplitter, QInputDialog, QFileDialog, QShortcut
)
from PyQt5.QtCore import Qt, QSize, QDir, QRegExp
from PyQt5.QtGui import (
    QIcon, QStandardItemModel, QStandardItem, QColor, QBrush, 
    QPainter, QPixmap, QFont, QKeySequence, QDesktopServices, QTextDocument,
    QTextCursor
)

# --- Matplotlib Integration ---
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from utils import db as command_db
from .dialogs import FuzzerDialog

# ==========================================
#       Viewers (Diff, Log, NMAP, Stats)
# ==========================================

class DiffViewer(QDialog):
    """
    GitHub-style Side-by-Side File Comparer.
    """
    def __init__(self, name_a, content_a, name_b, content_b, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Diff: {name_a} ↔ {name_b}")
        self.resize(1400, 900)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Pane
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_a = QLabel(f"🔴 {name_a}")
        lbl_a.setStyleSheet("font-weight: bold; color: #bf616a; font-size: 14px; padding: 5px;")
        self.text_left = QTextEdit()
        self.text_left.setReadOnly(True)
        self.configure_editor(self.text_left)
        left_layout.addWidget(lbl_a)
        left_layout.addWidget(self.text_left)
        
        # Right Pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        lbl_b = QLabel(f"🟢 {name_b}")
        lbl_b.setStyleSheet("font-weight: bold; color: #a3be8c; font-size: 14px; padding: 5px;")
        self.text_right = QTextEdit()
        self.text_right.setReadOnly(True)
        self.configure_editor(self.text_right)
        right_layout.addWidget(lbl_b)
        right_layout.addWidget(self.text_right)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter)
        
        # Sync Scroll
        sb_left = self.text_left.verticalScrollBar()
        sb_right = self.text_right.verticalScrollBar()
        sb_left.valueChanged.connect(sb_right.setValue)
        sb_right.valueChanged.connect(sb_left.setValue)
        
        # Zoom Shortcuts
        QShortcut(QKeySequence.ZoomIn, self, activated=self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.zoom_in)
        QShortcut(QKeySequence.ZoomOut, self, activated=self.zoom_out)

        self.compute_diff(content_a.splitlines(), content_b.splitlines())

    def configure_editor(self, editor):
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        editor.setFont(font)
        editor.setStyleSheet("QTextEdit { background-color: #1b2b42; color: #d8dee9; border: 1px solid #4c566a; }")
        editor.setLineWrapMode(QTextEdit.NoWrap)

    def compute_diff(self, lines_a, lines_b):
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        html_left = []
        html_right = []
        esc = html.escape
        
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'replace':
                for line in lines_a[i1:i2]: html_left.append(f"<div style='background-color: #4c252b;'>{esc(line)}</div>")
                for line in lines_b[j1:j2]: html_right.append(f"<div style='background-color: #254c30;'>{esc(line)}</div>")
            elif op == 'delete':
                for line in lines_a[i1:i2]: html_left.append(f"<div style='background-color: #4c252b;'>{esc(line)}</div>")
                for _ in range(i2-i1): html_right.append("<div>&nbsp;</div>")
            elif op == 'insert':
                for _ in range(j2-j1): html_left.append("<div>&nbsp;</div>")
                for line in lines_b[j1:j2]: html_right.append(f"<div style='background-color: #254c30;'>{esc(line)}</div>")
            elif op == 'equal':
                for line in lines_a[i1:i2]: html_left.append(f"<div>{esc(line)}</div>")
                for line in lines_b[j1:j2]: html_right.append(f"<div>{esc(line)}</div>")

        css = "font-family: Consolas, monospace; white-space: pre;"
        self.text_left.setHtml(f"<div style='{css}'>{''.join(html_left)}</div>")
        self.text_right.setHtml(f"<div style='{css}'>{''.join(html_right)}</div>")

    def zoom_in(self):
        self.text_left.zoomIn(1); self.text_right.zoomIn(1)
    def zoom_out(self):
        self.text_left.zoomOut(1); self.text_right.zoomOut(1)


class TerminalLogViewer(QDialog):
    """
    Enhanced Multi-Tab Viewer.
    """
    def __init__(self, file_paths, parent=None, working_directory=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        
        if isinstance(file_paths, str): self.file_paths = [file_paths]
        else: self.file_paths = file_paths
            
        self.setWindowTitle(f"Log Viewer - {len(self.file_paths)} file(s)")
        self.resize(1200, 800)
        
        layout = QVBoxLayout(self)

        # 1. Initialize Tabs EARLY (Fix for AttributeError)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        # 2. Toolbar
        toolbar = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find text or regex...")
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.textChanged.connect(self.reset_search_stats)
        self.search_input.setMinimumWidth(300)
        
        btn_prev = QPushButton("↑")
        btn_prev.setFixedWidth(30)
        btn_prev.clicked.connect(self.find_prev)

        btn_next = QPushButton("↓")
        btn_next.setFixedWidth(30)
        btn_next.clicked.connect(self.find_next)
        
        self.check_case = QCheckBox("Aa")
        self.check_regex = QCheckBox(".*")
        self.lbl_match_count = QLabel("")
        self.lbl_match_count.setStyleSheet("color: #888;")

        self.btn_add_file = QPushButton("+ Open File")
        self.btn_add_file.clicked.connect(self.add_files_dialog)

        self.btn_compare = QPushButton("Compare Tabs")
        self.btn_compare.clicked.connect(self.open_compare_dialog)
        
        # This call is now safe because self.tab_widget exists
        self.update_buttons_state()

        self.check_wrap = QCheckBox("Wrap")
        self.check_wrap.setChecked(True)
        self.check_wrap.toggled.connect(self.toggle_wrap)
        
        zoom_out = QPushButton("-")
        zoom_out.setFixedWidth(30)
        zoom_out.clicked.connect(self.zoom_out)

        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(30)
        zoom_in.clicked.connect(self.zoom_in)

        toolbar.addWidget(QLabel("🔍"))
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(btn_prev)
        toolbar.addWidget(btn_next)
        toolbar.addWidget(self.check_case)
        toolbar.addWidget(self.check_regex)
        toolbar.addWidget(self.lbl_match_count)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_add_file)
        toolbar.addWidget(self.btn_compare)
        toolbar.addWidget(self.check_wrap)
        toolbar.addWidget(QLabel("Zoom:"))
        toolbar.addWidget(zoom_out)
        toolbar.addWidget(zoom_in)
        
        layout.addLayout(toolbar)
        layout.addWidget(self.tab_widget)
        self.working_directory = working_directory
        
        # 3. Load Files
        for fp in self.file_paths:
            self.add_file_tab(fp)
            
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

        # Shortcuts
        QShortcut(QKeySequence.ZoomIn, self, activated=self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.zoom_in)
        QShortcut(QKeySequence.ZoomOut, self, activated=self.zoom_out)

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Files to View")
        start_dir = self.working_directory if self.working_directory else ""
        files, _ = QFileDialog.getOpenFileNames(self, "Open Files to View", start_dir)
        
        if files:
            for f in files:
                self.add_file_tab(f)

    def update_buttons_state(self):
        self.btn_compare.setEnabled(self.tab_widget.count() >= 2)

    def add_file_tab(self, file_path):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0,0,0,0)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        text_edit.setFont(font)
        text_edit.setStyleSheet("QTextEdit { background-color: #1b2b42; color: #d8dee9; border: none; selection-background-color: #4c566a; }")
        
        text_edit.setLineWrapMode(QTextEdit.WidgetWidth if self.check_wrap.isChecked() else QTextEdit.NoWrap)
        layout.addWidget(text_edit)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                tab.raw_content = content 
                html_content = self.ansi_to_html(content)
                text_edit.setHtml(f"<pre style='font-family: Consolas, monospace;'>{html_content}</pre>")
        except Exception as e:
            text_edit.setPlainText(f"Error: {e}")
            tab.raw_content = ""
            
        self.tab_widget.addTab(tab, os.path.basename(file_path))
        self.update_buttons_state()

    def close_tab(self, index):
        self.tab_widget.removeTab(index)
        self.update_buttons_state()
        if self.tab_widget.count() == 0: self.accept()

    def current_editor(self):
        w = self.tab_widget.currentWidget()
        return w.findChild(QTextEdit) if w else None

    # Search
    def find_next(self):
        editor = self.current_editor()
        if not editor: return
        text = self.search_input.text()
        if not text: return
        flags = QTextDocument.FindFlags()
        if self.check_case.isChecked(): flags |= QTextDocument.FindCaseSensitively
        if self.check_regex.isChecked():
            reg = QRegExp(text)
            if not self.check_case.isChecked(): reg.setCaseSensitivity(Qt.CaseInsensitive)
            found = editor.find(reg)
        else: found = editor.find(text, flags)
        if not found:
            editor.moveCursor(QTextCursor.Start) 
            if self.check_regex.isChecked(): found = editor.find(QRegExp(text))
            else: found = editor.find(text, flags)
            self.lbl_match_count.setText("Wrapped top" if found else "No matches")
        else: self.lbl_match_count.setText("Found")

    def find_prev(self):
        editor = self.current_editor()
        if not editor: return
        text = self.search_input.text()
        if not text: return
        if self.check_regex.isChecked():
             self.lbl_match_count.setText("Regex prev not supported")
             return
        flags = QTextDocument.FindFlags()
        if self.check_case.isChecked(): flags |= QTextDocument.FindCaseSensitively
        flags |= QTextDocument.FindBackward
        found = editor.find(text, flags)
        if not found:
            editor.moveCursor(QTextCursor.End)
            found = editor.find(text, flags)
            self.lbl_match_count.setText("Wrapped bottom" if found else "No matches")
        else: self.lbl_match_count.setText("Found")

    def reset_search_stats(self): self.lbl_match_count.setText("")
    def toggle_wrap(self, checked):
        for i in range(self.tab_widget.count()):
            e = self.tab_widget.widget(i).findChild(QTextEdit)
            if e: e.setLineWrapMode(QTextEdit.WidgetWidth if checked else QTextEdit.NoWrap)
            
    def zoom_in(self):
        e = self.current_editor()
        if e: e.zoomIn(1)
    def zoom_out(self):
        e = self.current_editor()
        if e: e.zoomOut(1)

    def ansi_to_html(self, text):
        text = html.escape(text)
        ansi_colors = {
            '30': '#3b4252', '31': '#bf616a', '32': '#a3be8c', '33': '#ebcb8b',
            '34': '#81a1c1', '35': '#b48ead', '36': '#88c0d0', '37': '#e5e9f0',
            '0': None,
        }
        pattern = re.compile(r'\x1b\[([\d;]+)m')
        parts = pattern.split(text)
        result = [parts[0]]
        current_span = False
        for i in range(1, len(parts), 2):
            codes = parts[i].split(';')
            color = None
            for c in codes:
                if c in ansi_colors: color = ansi_colors[c] if c != '0' else 'RESET'
            if color == 'RESET':
                if current_span: result.append("</span>"); current_span = False
            elif color:
                if current_span: result.append("</span>")
                result.append(f"<span style='color:{color};'>")
                current_span = True
            result.append(parts[i+1])
        if current_span: result.append("</span>")
        return "".join(result)

    def open_compare_dialog(self):
        cnt = self.tab_widget.count()
        if cnt < 2: return
        idx_a, idx_b = 0, 1
        if cnt > 2:
            items = [self.tab_widget.tabText(i) for i in range(cnt)]
            item, ok = QInputDialog.getItem(self, "Select File 2", 
                                            f"Compare '{self.tab_widget.tabText(self.tab_widget.currentIndex())}' with:", 
                                            items, 0, False)
            if ok and item:
                idx_a = self.tab_widget.currentIndex()
                for i in range(cnt):
                    if self.tab_widget.tabText(i) == item: idx_b = i; break
        
        name_a = self.tab_widget.tabText(idx_a)
        content_a = getattr(self.tab_widget.widget(idx_a), 'raw_content', "")
        name_b = self.tab_widget.tabText(idx_b)
        content_b = getattr(self.tab_widget.widget(idx_b), 'raw_content', "")
        
        viewer = DiffViewer(name_a, content_a, name_b, content_b, self)
        viewer.show()


# --- NMAP Viewer ---

class NmapViewer(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.file_path = file_path
        self.setWindowTitle(f"Nmap Report - {os.path.basename(file_path)}")
        self.resize(1100, 700)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.load_and_parse()
        layout.addWidget(QDialogButtonBox(QDialogButtonBox.Close, accepted=self.accept, rejected=self.accept))

    def load_and_parse(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f: content = f.read()
            lines = content.splitlines()
            current_host, current_ports, capture = None, [], False
            reports = {}
            regex = re.compile(r"^(\d+/(?:tcp|udp))\s+(\w+)\s+([^\s]+)\s*(.*)$")

            for line in lines:
                line = line.rstrip()
                if line.startswith("Nmap scan report for"):
                    if current_host and current_ports: reports[current_host] = current_ports
                    current_host = line.replace("Nmap scan report for", "").strip()
                    current_ports = []
                    capture = False
                    continue
                if "PORT" in line and "STATE" in line: capture = True; continue
                if not line and capture: capture = False; continue
                if capture:
                    m = regex.match(line)
                    if m: current_ports.append(m.groups())
            if current_host and current_ports: reports[current_host] = current_ports
            
            if not reports:
                self.layout().addWidget(QLabel("No structured Nmap data found."))
                return

            for host, rows in reports.items(): self.add_host_tab(host, rows)
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def add_host_tab(self, host, rows):
        tab = QWidget()
        l = QVBoxLayout(tab)
        tv = QTableView()
        m = QStandardItemModel()
        m.setHorizontalHeaderLabels(["PORT", "STATE", "SERVICE", "VERSION"])
        for p, st, sv, v in rows:
            si = QStandardItem(st)
            if "open" in st: si.setForeground(QColor("#a3be8c"))
            elif "filtered" in st: si.setForeground(QColor("#ebcb8b"))
            elif "closed" in st: si.setForeground(QColor("#bf616a"))
            m.appendRow([QStandardItem(p), si, QStandardItem(sv), QStandardItem(v)])
        tv.setModel(m)
        tv.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tv.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        tv.setSelectionBehavior(QAbstractItemView.SelectRows)
        tv.setAlternatingRowColors(True)
        l.addWidget(tv)
        self.tabs.addTab(tab, host.split(" ")[0])


# --- Helper Stats Classes ---

class StatsChartCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        is_dark = "dark" in parent.styleSheet().lower()
        if is_dark: plt.style.use('dark_background'); fc='#2e3440'
        else: plt.style.use('default'); fc='white'
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor=fc)
        self.axes = self.fig.add_subplot(111, facecolor=fc)
        if is_dark:
            self.axes.tick_params(axis='x', colors='white')
            self.axes.tick_params(axis='y', colors='white')
        super().__init__(self.fig)
        self.setParent(parent)
    def plot_bar_chart(self, labels, values, title):
        self.axes.clear()
        y = range(len(labels))
        self.axes.barh(y, values, color='#81a1c1')
        self.axes.set_yticks(y); self.axes.set_yticklabels(labels)
        self.axes.invert_yaxis(); self.axes.set_title(title)
        self.draw()
    def plot_pie_chart(self, labels, sizes, title):
        self.axes.clear()
        self.axes.pie(sizes, labels=labels, autopct='%1.1f%%')
        self.axes.set_title(title)
        self.draw()

class StatisticsDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.resize(800, 600)
        l = QVBoxLayout(self)
        self.chart = StatsChartCanvas(parent=self)
        l.addWidget(self.chart)
        codes = [self.model.item(r, 5).text() for r in range(self.model.rowCount()) if self.model.item(r, 5)]
        c = Counter(codes)
        if c: self.chart.plot_pie_chart(list(c.keys()), list(c.values()), "Status Codes")
        l.addWidget(QDialogButtonBox(QDialogButtonBox.Ok, accepted=self.accept))

class RiskAnalysisDialog(QDialog):
    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.resize(600, 500)
        l = QVBoxLayout(self)
        t = QTextEdit(); t.setReadOnly(True)
        l.addWidget(t)
        h = "<h3>Analysis Report</h3><ul>"
        for u in urls[:50]: h += f"<li style='color:{'#bf616a' if 'admin' in u else '#d8dee9'}'>{u}</li>"
        t.setHtml(h + "</ul>")

class NumericStandardItem(QStandardItem):
    def __lt__(self, other):
        try: return int(self.text()) < int(other.text())
        except: return self.text() < other.text()

class PlaygroundWindow(QDialog):
    def __init__(self, file_paths, terminal_widget, working_directory, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.file_paths = file_paths
        self.terminal_widget = terminal_widget
        self.working_directory = working_directory
        self.starred_hosts = set()
        self.starred_hosts_file = os.path.join(working_directory, "starred_hosts.txt")
        self.load_starred()
        self.setWindowTitle(f"Structured Viewer - {len(file_paths)} files")
        self.resize(1100, 700)
        l = QVBoxLayout(self)
        tb = QHBoxLayout()
        b1 = QPushButton("Risks"); b1.clicked.connect(lambda: RiskAnalysisDialog([self.get_url(r) for r in range(self.model.rowCount())], self).exec_())
        b2 = QPushButton("Stats"); b2.clicked.connect(lambda: StatisticsDialog(self.model, self).exec_())
        tb.addWidget(b1); tb.addStretch(); tb.addWidget(b2)
        l.addLayout(tb)
        self.tv = QTableView(); self.tv.setSortingEnabled(True)
        l.addWidget(self.tv)
        self.model = QStandardItemModel()
        self.model.itemChanged.connect(self.on_change)
        self.load_data()
        self.tv.setModel(self.model)
        self.tv.resizeColumnsToContents()
        self.tv.doubleClicked.connect(lambda i: webbrowser.open(self.get_url(i.row())) if i.column()==2 else None)

    def load_starred(self):
        if os.path.exists(self.starred_hosts_file):
            with open(self.starred_hosts_file) as f: self.starred_hosts = set(x.strip() for x in f)
    def save_starred(self):
        with open(self.starred_hosts_file, 'w') as f: f.write('\n'.join(sorted(self.starred_hosts)))
    def on_change(self, item):
        if item.column() == 0:
            h = self.model.item(item.row(), 2).text()
            if item.checkState() == Qt.Checked: self.starred_hosts.add(h)
            else: self.starred_hosts.discard(h)
            self.save_starred()
    def get_url(self, r):
        return f"{self.model.item(r,1).text()}://{self.model.item(r,2).text()}{self.model.item(r,3).text()}"
    def load_data(self):
        self.model.setHorizontalHeaderLabels(['⭐', 'Schema', 'Host', 'Path', 'Ext', 'Status', 'Length', 'Tech'])
        re_line = re.compile(r"^(?P<url>https?://[^\s]+)\s+\[\s*(?P<status_code>[\d,\s]+)\s*\]\s+\[\s*(?P<length>\d+)\s*\]")
        ansi = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        for fp in self.file_paths:
            try:
                with open(fp, errors='ignore') as f:
                    for line in f:
                        m = re_line.match(ansi.sub('', line).strip())
                        if not m: continue
                        d = m.groupdict(); p = urlparse(d['url'])
                        tm = re.search(r"\[\s*([^\]]+)\s*\]$", line)
                        tech = tm.group(1) if tm and "]" not in d['length'] else ""
                        si = QStandardItem(); si.setCheckable(True)
                        if p.hostname in self.starred_hosts: si.setCheckState(Qt.Checked)
                        st = int(d['status_code'].split(',')[-1])
                        sti = NumericStandardItem(str(st))
                        if 200<=st<300: sti.setForeground(QColor("#a3be8c"))
                        elif 300<=st<400: sti.setForeground(QColor("#81a1c1"))
                        elif 400<=st<500: sti.setForeground(QColor("#ebcb8b"))
                        elif 500<=st<600: sti.setForeground(QColor("#bf616a"))
                        self.model.appendRow([si, QStandardItem(p.scheme), QStandardItem(p.hostname), QStandardItem(p.path), QStandardItem(os.path.splitext(p.path)[1]), sti, NumericStandardItem(d['length']), QStandardItem(tech)])
            except: pass

# ==========================================
#       PlaygroundTabWidget (Main)
# ==========================================

class PlaygroundTabWidget(QWidget):
    RECON_FILES = {'naabu_out', 'nmap_out', 'nmap_targets.txt', 'nmap_udp_out'}
    SETTINGS_FILES = {'scope.txt', 'domains', 'project_data.db'}

    def __init__(self, working_directory, icon_path, terminal_widget, hostname_test=False, parent=None):
        super().__init__(parent)
        self.root_directory = working_directory
        self.current_path = working_directory
        self.icon_path = icon_path
        self.terminal_widget = terminal_widget
        self.font_size = 12
        self.bg_pixmap = None
        
        if hostname_test:
            bp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes/img/pokemon/playground_bg.png")
            if os.path.exists(bp): self.bg_pixmap = QPixmap(bp)

        l = QVBoxLayout(self); l.setContentsMargins(5,5,5,5)
        
        nl = QHBoxLayout()
        b_home = QToolButton(); b_home.setText("🏠"); b_home.clicked.connect(self.go_home)
        b_up = QToolButton(); b_up.setText("⬆"); b_up.clicked.connect(self.go_up)
        self.path_edit = QLineEdit(); self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet("QLineEdit { background-color: #2e3440; color: #d8dee9; border: 1px solid #4c566a; }")
        b_ref = QToolButton(); b_ref.setText("↻"); b_ref.clicked.connect(self.refresh_playground)
        nl.addWidget(b_home); nl.addWidget(b_up); nl.addWidget(self.path_edit); nl.addWidget(b_ref)
        l.addLayout(nl)

        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.itemDoubleClicked.connect(self.on_dclick)
        self.tree.customContextMenuRequested.connect(self.on_ctx)
        f = self.tree.font(); f.setPointSize(12); self.tree.setFont(f); self.tree.setIconSize(QSize(24,24))
        
        if self.bg_pixmap:
            self.tree.setStyleSheet("QTreeWidget { background: transparent; border: none; } QTreeWidget::item { color: white; } QTreeWidget::item:selected { background: #81a1c1; border: 1px solid #81a1c1; }")
        else: self.tree.setStyleSheet("QTreeWidget::item { padding: 4px; }")
        l.addWidget(self.tree)
        
        bl = QHBoxLayout()
        b_open = QPushButton("Open Selected"); b_open.clicked.connect(self.open_smart)
        bl.addStretch(); bl.addWidget(b_open)
        l.addLayout(bl)
        self.refresh_playground()

    def paintEvent(self, e):
        if self.bg_pixmap: QPainter(self).drawPixmap(self.rect(), self.bg_pixmap)
        else: super().paintEvent(e)

    def go_up(self):
        p = os.path.dirname(self.current_path)
        if p and os.path.exists(p): self.current_path = p; self.refresh_playground()
    def go_home(self): self.current_path = self.root_directory; self.refresh_playground()

    def refresh_playground(self):
        self.tree.clear(); self.path_edit.setText(self.current_path)
        ic_f = self.get_icon("folder.svg", QStyle.SP_DirIcon)
        ic_fi = self.get_icon("file.svg", QStyle.SP_FileIcon)
        ic_b = self.get_icon("bag.svg", QStyle.SP_DirClosedIcon)
        ic_c = self.get_icon("category.svg", QStyle.SP_FileDialogListView)

        try:
            entries = sorted(os.scandir(self.current_path), key=lambda e: (not e.is_dir(), e.name.lower()))
            recon, settings = None, None
            udirs, ufiles = [], []

            for e in entries:
                if e.name in self.SETTINGS_FILES:
                    if not settings:
                        settings = QTreeWidgetItem(self.tree, ["Project Settings"])
                        settings.setIcon(0, ic_c); settings.setData(0, Qt.UserRole+1, "virtual"); settings.setExpanded(True)
                    self.add_item(settings, e, ic_fi)
                    continue
                if e.name in self.RECON_FILES:
                    if not recon:
                        recon = QTreeWidgetItem(self.tree, ["Reconnaissance Data"])
                        recon.setIcon(0, ic_c); recon.setData(0, Qt.UserRole+1, "virtual"); recon.setExpanded(True)
                    self.add_item(recon, e, ic_fi)
                    continue
                if e.is_dir():
                    if e.name in ["exploits", "reports"]:
                        i = QTreeWidgetItem(self.tree, [e.name.capitalize()])
                        i.setIcon(0, ic_f); i.setData(0, Qt.UserRole, e.path); i.setData(0, Qt.UserRole+1, "dir")
                        continue
                    udirs.append(e)
                else: ufiles.append(e)

            for d in udirs:
                i = QTreeWidgetItem(self.tree, [d.name])
                i.setIcon(0, ic_f); i.setData(0, Qt.UserRole, d.path); i.setData(0, Qt.UserRole+1, "dir")

            bags = {}
            for f in ufiles:
                if "_" in f.name:
                    pre = f.name.split('_')[0]
                    if pre not in bags:
                        bags[pre] = QTreeWidgetItem(self.tree, [pre])
                        bags[pre].setIcon(0, ic_b); bags[pre].setData(0, Qt.UserRole+1, "bag")
                    self.add_item(bags[pre], f, ic_fi)
                else: self.add_item(self.tree, f, ic_fi)
        except Exception as e: QTreeWidgetItem(self.tree, [f"Error: {e}"])

    def add_item(self, parent, entry, icon):
        i = QTreeWidgetItem(parent, [entry.name])
        i.setIcon(0, icon); i.setData(0, Qt.UserRole, entry.path); i.setData(0, Qt.UserRole+1, "file")

    def get_icon(self, n, fallback):
        p = os.path.join(self.icon_path, n)
        return QIcon(p) if os.path.exists(p) else self.style().standardIcon(fallback)

    def on_dclick(self, item, col):
        t = item.data(0, Qt.UserRole+1); p = item.data(0, Qt.UserRole)
        if t == "dir": self.current_path = p; self.refresh_playground()
        elif t in ["bag", "virtual"]: item.setExpanded(not item.isExpanded())
        elif t == "file": self.open_smart(item)

    def open_smart(self, item=None):
        items = [item] if item else self.tree.selectedItems()
        files = [i for i in items if i.data(0, Qt.UserRole+1) == "file"]
        if not files: return
        
        fp = files[0].data(0, Qt.UserRole)
        if os.path.basename(fp).startswith("nmap_") or self.is_nmap(fp):
            NmapViewer(fp, self).show(); return
        
        # Check if structured
        try:
            with open(fp, errors='ignore') as f:
                if re.match(r"^https?://[^\s]+\s+\[", re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', f.readline())):
                    PlaygroundWindow([f.data(0, Qt.UserRole) for f in files], self.terminal_widget, self.current_path, self).show()
                    return
        except: pass
        
        TerminalLogViewer([f.data(0, Qt.UserRole) for f in files], self, working_directory=self.current_path).show()

    def is_nmap(self, p):
        try:
            with open(p, errors='ignore') as f: return "Nmap scan" in f.read(512)
        except: return False

    def on_ctx(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        t = item.data(0, Qt.UserRole+1); p = item.data(0, Qt.UserRole)
        m = QMenu()
        
        if t == "dir":
            m.addAction("Open Folder").triggered.connect(lambda: setattr(self, 'current_path', p) or self.refresh_playground())
        elif t == "file":
            sel = self.tree.selectedItems()
            if len(sel) == 2:
                m.addAction("Compare Selected Files").triggered.connect(lambda: DiffViewer(sel[0].text(0), self.read_file(sel[0]), sel[1].text(0), self.read_file(sel[1]), self).show())
                m.addSeparator()
            m.addAction("Open (Smart)").triggered.connect(lambda: self.open_smart(item))
        m.exec_(self.tree.viewport().mapToGlobal(pos))

    def read_file(self, item):
        try: 
            with open(item.data(0, Qt.UserRole), errors='replace') as f: return f.read()
        except: return ""

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.font_size = max(8, min(30, self.font_size + (1 if e.angleDelta().y() > 0 else -1)))
            f = self.tree.font(); f.setPointSize(self.font_size); self.tree.setFont(f)
            self.tree.setIconSize(QSize(self.font_size+12, self.font_size+12))
