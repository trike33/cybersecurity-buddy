import os
import re
import html
import sys
import shutil
from urllib.parse import urlparse
from collections import Counter
import webbrowser
import subprocess

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDialog,
    QTableView, QHeaderView, QMessageBox, QPushButton, QHBoxLayout,
    QTextEdit, QDialogButtonBox, QTabWidget, QListWidget, QLabel, QMenu,
    QStyleOption, QStyle, QLineEdit, QCheckBox, QApplication, QFrame,
    QFileSystemModel, QAction, QToolButton, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize, QDir
from PyQt5.QtGui import (
    QIcon, QStandardItemModel, QStandardItem, QColor, QBrush, 
    QPainter, QPixmap, QFont, QKeySequence, QDesktopServices
)

# --- Matplotlib Integration ---
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from utils import db as command_db
from .dialogs import FuzzerDialog

# ==========================================
#       Viewers (Log, Stats, Table, NMAP)
# ==========================================

class TerminalLogViewer(QDialog):
    """Robust viewer for raw terminal output files with ANSI color support."""
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Log Viewer - {os.path.basename(file_path)}")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find...")
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.setMaximumWidth(300)
        
        self.btn_prev = QPushButton("↑")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(self.find_prev)

        self.btn_next = QPushButton("↓")
        self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(self.find_next)
        
        self.check_wrap = QCheckBox("Word Wrap")
        self.check_wrap.setChecked(True)
        self.check_wrap.toggled.connect(self.toggle_wrap)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedWidth(30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)

        toolbar_layout.addWidget(QLabel("Search:"))
        toolbar_layout.addWidget(self.search_input)
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.check_wrap)
        toolbar_layout.addWidget(QLabel("Zoom:"))
        toolbar_layout.addWidget(self.zoom_out_btn)
        toolbar_layout.addWidget(self.zoom_in_btn)
        
        layout.addLayout(toolbar_layout)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)
        
        # Dark theme
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1b2b42; 
                color: #d8dee9; 
                border: 2px solid #2e3440;
                selection-background-color: #4c566a;
            }
        """)
        
        layout.addWidget(self.text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

        self.load_file_content()

    def load_file_content(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                html_content = self.ansi_to_html(content)
                self.text_edit.setHtml(f"<pre style='font-family: Consolas, monospace;'>{html_content}</pre>")
        except Exception as e:
            self.text_edit.setPlainText(f"Error reading file:\n{e}")

    def ansi_to_html(self, text):
        text = html.escape(text)
        ansi_colors = {
            '30': '#3b4252', '31': '#bf616a', '32': '#a3be8c', '33': '#ebcb8b',
            '34': '#81a1c1', '35': '#b48ead', '36': '#88c0d0', '37': '#e5e9f0',
            '90': '#4c566a', '91': '#d08770', '92': '#a3be8c', '93': '#ebcb8b',
            '94': '#5e81ac', '95': '#b48ead', '96': '#8fbcbb', '97': '#eceff4',
            '0': None,
        }
        pattern = re.compile(r'\x1b\[([\d;]+)m')
        parts = pattern.split(text)
        result = []
        current_span_open = False
        result.append(parts[0])

        for i in range(1, len(parts), 2):
            codes = parts[i].split(';')
            text_chunk = parts[i+1]
            color_code = None
            for c in codes:
                if c in ansi_colors:
                    if c == '0': color_code = 'RESET'
                    else: color_code = ansi_colors[c]

            if color_code == 'RESET':
                if current_span_open:
                    result.append("</span>")
                    current_span_open = False
            elif color_code:
                if current_span_open: result.append("</span>")
                result.append(f"<span style='color:{color_code};'>")
                current_span_open = True
            result.append(text_chunk)
            
        if current_span_open: result.append("</span>")
        return "".join(result)

    def toggle_wrap(self, checked):
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth if checked else QTextEdit.NoWrap)

    def find_next(self):
        self.text_edit.find(self.search_input.text())

    def find_prev(self):
        self.text_edit.find(self.search_input.text(), QTextEdit.FindBackward)

    def zoom_in(self): self.text_edit.zoomIn(1)
    def zoom_out(self): self.text_edit.zoomOut(1)

# --- NMAP Viewer (New) ---

class NmapViewer(QDialog):
    """
    Parses Nmap -oN output and displays results in tabs (one per host).
    Parses into columns: PORT, STATE, SERVICE, VERSION.
    """
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Nmap Report - {os.path.basename(file_path)}")
        self.resize(900, 600)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.load_and_parse()
        
        # Close Button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def load_and_parse(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Split content by Nmap reports
            # Regex looks for "Nmap scan report for <host>"
            # We iterate line by line to maintain state
            lines = content.splitlines()
            current_host = None
            current_ports = []
            capture_ports = False
            
            reports = {} # { "Host Name": [ (port, state, service, version), ... ] }

            # Regex for port line: 80/tcp open  http    SimpleHTTPServer 0.6
            port_regex = re.compile(r"^(\d+/(?:tcp|udp))\s+(\w+)\s+([^\s]+)\s*(.*)$")

            for line in lines:
                line = line.rstrip()
                
                # Detect Host
                if line.startswith("Nmap scan report for"):
                    # Save previous if exists
                    if current_host and current_ports:
                        reports[current_host] = current_ports
                    
                    # Start new
                    current_host = line.replace("Nmap scan report for", "").strip()
                    current_ports = []
                    capture_ports = False
                    continue
                
                # Detect Start of Table
                if "PORT" in line and "STATE" in line and "SERVICE" in line:
                    capture_ports = True
                    continue
                
                # Stop capturing if we hit a blank line or headers (end of table usually)
                if not line and capture_ports:
                    capture_ports = False
                    continue
                
                if capture_ports:
                    match = port_regex.match(line)
                    if match:
                        port, state, service, version = match.groups()
                        current_ports.append((port, state, service, version))

            # Save last block
            if current_host and current_ports:
                reports[current_host] = current_ports
            
            if not reports:
                layout = QVBoxLayout()
                lbl = QLabel("No structured Nmap data found.\n(This viewer supports standard -oN output)")
                lbl.setAlignment(Qt.AlignCenter)
                self.layout().addWidget(lbl)
                return

            # Build UI
            for host, rows in reports.items():
                self.add_host_tab(host, rows)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse Nmap file:\n{e}")

    def add_host_tab(self, host, rows):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        table = QTableView()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["PORT", "STATE", "SERVICE", "VERSION"])
        
        for p, st, sv, v in rows:
            # Colorize State
            state_item = QStandardItem(st)
            if "open" in st:
                state_item.setForeground(QColor("#a3be8c")) # Green
            elif "filtered" in st:
                state_item.setForeground(QColor("#ebcb8b")) # Yellow
            elif "closed" in st:
                state_item.setForeground(QColor("#bf616a")) # Red
                
            model.appendRow([
                QStandardItem(p),
                state_item,
                QStandardItem(sv),
                QStandardItem(v)
            ])
            
        table.setModel(model)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch) # Stretch Version column
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        
        # Style
        table.setStyleSheet("QTableView { gridline-color: #4c566a; }")

        layout.addWidget(table)
        self.tabs.addTab(tab, host.split(" ")[0]) # Shorten tab name if IP is long

# --- Statistics & Charts ---

class StatsChartCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        is_dark_theme = "dark" in parent.styleSheet().lower()
        if is_dark_theme:
            plt.style.use('dark_background')
            self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#2e3440')
            self.axes = self.fig.add_subplot(111, facecolor='#2e3440')
            self.axes.tick_params(axis='x', colors='white')
            self.axes.tick_params(axis='y', colors='white')
        else:
            plt.style.use('default')
            self.fig = Figure(figsize=(width, height), dpi=dpi)
            self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

    def plot_bar_chart(self, labels, values, title, xlabel='Count'):
        self.axes.clear()
        y_pos = range(len(labels))
        self.axes.barh(y_pos, values, align='center', color='#81a1c1', height=0.6)
        self.axes.set_yticks(y_pos)
        self.axes.set_yticklabels(labels, fontsize=9)
        self.axes.invert_yaxis()
        self.axes.set_xlabel(xlabel)
        self.axes.set_title(title)
        self.fig.tight_layout()
        self.draw()

    def plot_pie_chart(self, labels, sizes, title):
        self.axes.clear()
        self.axes.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
        self.axes.set_title(title)
        self.fig.tight_layout()
        self.draw()

class StatisticsDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Dataset Statistics")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.chart_canvas = StatsChartCanvas(parent=self)
        layout.addWidget(self.chart_canvas)
        
        codes = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 5) # Status code col
            if item: codes.append(item.text())
        
        counts = Counter(codes)
        labels = list(counts.keys())
        sizes = list(counts.values())
        if labels:
            self.chart_canvas.plot_pie_chart(labels, sizes, "Status Codes")
            
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

class RiskAnalysisDialog(QDialog):
    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Risk Analysis")
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        
        html_out = "<h3>Analysis Report</h3><ul>"
        for url in urls[:50]: 
            if "admin" in url: html_out += f"<li style='color:#bf616a'>{url} (High Risk)</li>"
            else: html_out += f"<li>{url}</li>"
        html_out += "</ul>"
        self.text.setHtml(html_out)

# --- Playground Window (Structured Table) ---

class NumericStandardItem(QStandardItem):
    def __lt__(self, other):
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return self.text() < other.text()

class PlaygroundWindow(QDialog):
    """Structured Viewer for httpx/table data."""
    def __init__(self, file_paths, terminal_widget, working_directory, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.terminal_widget = terminal_widget
        self.working_directory = working_directory
        self.starred_hosts = set()
        self.starred_hosts_file = os.path.join(self.working_directory, "starred_hosts.txt")
        self.load_starred_hosts()       
        
        title = f"Structured Viewer - {os.path.basename(file_paths[0])}"
        if len(file_paths) > 1: title += f" (+{len(file_paths)-1} others)"
        self.setWindowTitle(title)
        self.setGeometry(150, 150, 1100, 700)

        main_layout = QVBoxLayout(self)
        
        # Toolbar
        top_bar = QHBoxLayout()
        self.risk_btn = QPushButton("Analyze Risks")
        self.risk_btn.clicked.connect(self.show_risk_analysis)
        self.stats_btn = QPushButton("View Stats")
        self.stats_btn.clicked.connect(self.show_stats)
        
        top_bar.addWidget(self.risk_btn)
        top_bar.addStretch()
        top_bar.addWidget(self.stats_btn)
        main_layout.addLayout(top_bar)
        
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)
        main_layout.addWidget(self.table_view)
        
        self.model = QStandardItemModel()
        self.model.itemChanged.connect(self.on_item_changed)
        self.load_and_parse_data()
        
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.open_context_menu)
        self.table_view.doubleClicked.connect(self.on_cell_double_clicked)

    def load_starred_hosts(self):
        if os.path.exists(self.starred_hosts_file):
            try:
                with open(self.starred_hosts_file, 'r') as f:
                    self.starred_hosts = set(line.strip() for line in f)
            except: pass

    def save_starred_hosts(self):
        try:
            with open(self.starred_hosts_file, 'w') as f:
                for host in sorted(list(self.starred_hosts)):
                    f.write(host + '\n')
        except: pass

    def on_item_changed(self, item):
        if item.column() == 0:
            row = item.row()
            host_item = self.model.item(row, 2)
            if host_item:
                host = host_item.text()
                if item.checkState() == Qt.Checked: self.starred_hosts.add(host)
                else: self.starred_hosts.discard(host)
                self.save_starred_hosts()

    def get_url_from_row(self, row):
        schema = self.model.item(row, 1).text()
        host = self.model.item(row, 2).text()
        path = self.model.item(row, 3).text()
        return f"{schema}://{host}{path}"

    def load_and_parse_data(self):
        self.all_records = [rec for fp in self.file_paths for rec in self.parse_httpx_file(fp)]
        headers = ['⭐', 'Schema', 'Host', 'Path', 'Ext', 'Status', 'Length', 'Tech']
        self.model.setHorizontalHeaderLabels(headers)

        for record in self.all_records:
            host = record.get('host', '')
            star_item = QStandardItem()
            star_item.setCheckable(True)
            star_item.setCheckState(Qt.Checked if host in self.starred_hosts else Qt.Unchecked)
            
            status = int(record.get('status_code', 0))
            status_item = NumericStandardItem(str(status))
            if 200 <= status < 300: status_item.setForeground(QColor("#a3be8c"))
            elif 300 <= status < 400: status_item.setForeground(QColor("#81a1c1"))
            elif 400 <= status < 500: status_item.setForeground(QColor("#ebcb8b"))
            elif 500 <= status < 600: status_item.setForeground(QColor("#bf616a"))

            row = [
                star_item,
                QStandardItem(record.get('schema')),
                QStandardItem(host),
                QStandardItem(record.get('path')),
                QStandardItem(record.get('extension')),
                status_item,
                NumericStandardItem(str(record.get('length'))),
                QStandardItem(record.get('technology'))
            ]
            self.model.appendRow(row)

        self.table_view.setModel(self.model)
        self.table_view.resizeColumnsToContents()
        self.table_view.setColumnWidth(0, 30)

    def parse_httpx_file(self, file_path):
        records = []
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        line_regex = re.compile(
            r"^(?P<url>https?://[^\s]+)\s+"
            r"\[\s*(?P<status_code>[\d,\s]+)\s*\]\s+"
            r"\[\s*(?P<length>\d+)\s*\]"
        )
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    clean = ansi_escape.sub('', line).strip()
                    match = line_regex.match(clean)
                    if not match: continue
                    data = match.groupdict()
                    parsed = urlparse(data['url'])
                    
                    tech_match = re.search(r"\[\s*([^\]]+)\s*\]$", clean)
                    tech = tech_match.group(1) if tech_match and "]" not in data['length'] else ""

                    records.append({
                        'schema': parsed.scheme, 'host': parsed.hostname, 'path': parsed.path,
                        'extension': os.path.splitext(parsed.path)[1], 
                        'status_code': data['status_code'].split(',')[-1],
                        'length': data['length'], 'technology': tech
                    })
        except: pass
        return records

    def on_cell_double_clicked(self, index):
        if index.column() == 2: self.open_in_browser(index.row())

    def open_context_menu(self, pos):
        idx = self.table_view.indexAt(pos)
        if not idx.isValid(): return
        menu = QMenu()
        menu.addAction("Open in Browser").triggered.connect(lambda: self.open_in_browser(idx.row()))
        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def open_in_browser(self, row):
        webbrowser.open(self.get_url_from_row(row))

    def show_risk_analysis(self):
        urls = [f"{rec['schema']}://{rec['host']}{rec['path']}" for rec in self.all_records]
        RiskAnalysisDialog(urls, self).exec_()

    def show_stats(self):
        StatisticsDialog(self.model, self).exec_()


# ==========================================
#       REFACTORED: PlaygroundTabWidget
# ==========================================

class PlaygroundTabWidget(QWidget):
    """
    Explorer-style File Viewer with Virtual Categories.
    Features:
    - Virtual Categories for 'Recon' and 'Settings'.
    - Auto-detection for file opening (Nmap, Httpx/Structured, or Raw Log).
    - Bagging for cluttered output files.
    """
    
    # Virtual Grouping Rules (Exact filenames)
    RECON_FILES = {'naabu_out', 'nmap_out', 'nmap_targets.txt', 'nmap_udp_out'}
    SETTINGS_FILES = {'scope.txt', 'domains.txt', 'project_data.db'}

    def __init__(self, working_directory, icon_path, terminal_widget, hostname_test=False, parent=None):
        super().__init__(parent)
        self.root_directory = working_directory
        self.current_path = working_directory
        self.icon_path = icon_path
        self.terminal_widget = terminal_widget
        
        self.font_size = 12
        
        # --- Background Image Setup ---
        self.bg_pixmap = None
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bg_path = os.path.join(base_path, "themes", "img", "pokemon", "playground_bg.png")
        if os.path.exists(bg_path) and hostname_test == True:
            self.bg_pixmap = QPixmap(bg_path)

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 1. Navigation Bar
        nav_layout = QHBoxLayout()
        self.btn_home = QToolButton()
        self.btn_home.setText("🏠")
        self.btn_home.setToolTip("Root")
        self.btn_home.clicked.connect(self.go_home)

        self.btn_up = QToolButton()
        self.btn_up.setText("⬆")
        self.btn_up.setToolTip("Up")
        self.btn_up.clicked.connect(self.go_up)
        
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet("QLineEdit { background-color: #2e3440; color: #d8dee9; border: 1px solid #4c566a; border-radius: 4px; padding: 4px; }")

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("↻")
        self.btn_refresh.setToolTip("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_playground)

        nav_layout.addWidget(self.btn_home)
        nav_layout.addWidget(self.btn_up)
        nav_layout.addWidget(self.path_edit)
        nav_layout.addWidget(self.btn_refresh)
        layout.addLayout(nav_layout)

        # 2. Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree_widget.customContextMenuRequested.connect(self.open_context_menu)

        font = self.tree_widget.font()
        font.setPointSize(self.font_size)
        self.tree_widget.setFont(font)
        self.tree_widget.setIconSize(QSize(24, 24))
        
        # Styling for transparency if bg is present
        if self.bg_pixmap:
            self.tree_widget.setStyleSheet("""
                QTreeWidget { background-color: transparent; border: none; }
                QTreeWidget::item { color: #ffffff; padding: 4px; } 
                QTreeWidget::item:hover { background-color: rgba(255, 255, 255, 0.1); }
                QTreeWidget::item:selected { background-color: rgba(129, 161, 193, 0.4); border: 1px solid #81a1c1; }
            """)
        else:
             self.tree_widget.setStyleSheet("QTreeWidget::item { padding: 4px; }")

        layout.addWidget(self.tree_widget)
        
        # 3. Bottom Bar
        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self.open_smart)
        btn_layout.addStretch()
        btn_layout.addWidget(open_btn)
        layout.addLayout(btn_layout)
        
        self.refresh_playground()

    def paintEvent(self, event):
        if self.bg_pixmap and not self.bg_pixmap.isNull():
            opt = QStyleOption()
            opt.initFrom(self)
            p = QPainter(self)
            p.drawPixmap(self.rect(), self.bg_pixmap)
        else:
            super().paintEvent(event)

    def go_up(self):
        parent = os.path.dirname(self.current_path)
        if parent and os.path.exists(parent):
            self.current_path = parent
            self.refresh_playground()

    def go_home(self):
        self.current_path = self.root_directory
        self.refresh_playground()

    def refresh_playground(self):
        self.tree_widget.clear()
        self.path_edit.setText(self.current_path)
        
        # --- Icons ---
        folder_icon = self.get_icon("folder.svg", QStyle.SP_DirIcon)
        file_icon = self.get_icon("file.svg", QStyle.SP_FileIcon)
        bag_icon = self.get_icon("bag.svg", QStyle.SP_DirClosedIcon)
        
        # Using "category.svg" for Virtual Groups
        category_icon = self.get_icon("category.svg", QStyle.SP_FileDialogListView)
        
        try:
            entries = sorted(os.scandir(self.current_path), key=lambda e: (not e.is_dir(), e.name.lower()))
            
            # --- Containers (Virtual Items) ---
            recon_group_item = None
            settings_group_item = None
            
            unorganized_dirs = []
            unorganized_files = []

            # --- Sorting Logic ---
            for entry in entries:
                name = entry.name
                
                # 1. Project Settings
                if name in self.SETTINGS_FILES:
                    if not settings_group_item:
                        settings_group_item = QTreeWidgetItem(self.tree_widget)
                        settings_group_item.setText(0, "Project Settings")
                        settings_group_item.setIcon(0, category_icon) 
                        settings_group_item.setData(0, Qt.UserRole + 1, "virtual_group")
                        settings_group_item.setExpanded(True)
                    
                    self.add_file_child(settings_group_item, entry, file_icon)
                    continue

                # 2. Recon Data
                if name in self.RECON_FILES:
                    if not recon_group_item:
                        recon_group_item = QTreeWidgetItem(self.tree_widget)
                        recon_group_item.setText(0, "Reconnaissance Data")
                        recon_group_item.setIcon(0, category_icon) 
                        recon_group_item.setData(0, Qt.UserRole + 1, "virtual_group")
                        recon_group_item.setExpanded(True)
                    
                    self.add_file_child(recon_group_item, entry, file_icon)
                    continue

                # 3. Special Real Folders (Exploits, Reports)
                if entry.is_dir():
                    if name == "exploits":
                        item = QTreeWidgetItem(self.tree_widget)
                        item.setText(0, "Exploits")
                        item.setIcon(0, folder_icon)
                        item.setData(0, Qt.UserRole, entry.path)
                        item.setData(0, Qt.UserRole + 1, "dir")
                        continue
                        
                    if name == "reports":
                        item = QTreeWidgetItem(self.tree_widget)
                        item.setText(0, "Reports")
                        item.setIcon(0, folder_icon)
                        item.setData(0, Qt.UserRole, entry.path)
                        item.setData(0, Qt.UserRole + 1, "dir")
                        continue
                    
                    unorganized_dirs.append(entry)
                else:
                    unorganized_files.append(entry)

            # --- Render Unorganized Items ---
            for d in unorganized_dirs:
                item = QTreeWidgetItem(self.tree_widget)
                item.setText(0, d.name)
                item.setIcon(0, folder_icon)
                item.setData(0, Qt.UserRole, d.path)
                item.setData(0, Qt.UserRole + 1, "dir")

            bags = {}
            for entry in unorganized_files:
                name = entry.name
                if "_" in name:
                    prefix = name.split('_')[0]
                    if prefix not in bags:
                        bag_item = QTreeWidgetItem(self.tree_widget)
                        bag_item.setText(0, prefix)
                        bag_item.setIcon(0, bag_icon)
                        bag_item.setData(0, Qt.UserRole + 1, "bag")
                        bags[prefix] = bag_item
                    self.add_file_child(bags[prefix], entry, file_icon)
                else:
                    self.add_file_child(self.tree_widget, entry, file_icon)
            
        except Exception as e:
            err_item = QTreeWidgetItem(self.tree_widget)
            err_item.setText(0, f"Error: {e}")

    def add_file_child(self, parent, entry, icon):
        item = QTreeWidgetItem(parent)
        item.setText(0, entry.name)
        item.setIcon(0, icon)
        item.setData(0, Qt.UserRole, entry.path)
        item.setData(0, Qt.UserRole + 1, "file")

    def get_icon(self, filename, fallback_standard_icon):
        path = os.path.join(self.icon_path, filename)
        if self.icon_path and os.path.exists(path):
            return QIcon(path)
        return self.style().standardIcon(fallback_standard_icon)

    # --- Interaction Logic ---

    def on_item_double_clicked(self, item, column):
        item_type = item.data(0, Qt.UserRole + 1)
        path = item.data(0, Qt.UserRole)

        if item_type == "dir":
            self.current_path = path
            self.refresh_playground()
        elif item_type in ["bag", "virtual_group"]:
            item.setExpanded(not item.isExpanded())
        elif item_type == "file":
            self.open_smart(specific_item=item)

    def open_smart(self, specific_item=None):
        if specific_item: items = [specific_item]
        else: items = self.tree_widget.selectedItems()
        
        if not items: return
        file_items = [i for i in items if i.data(0, Qt.UserRole + 1) == "file"]
        if not file_items: return

        first_path = file_items[0].data(0, Qt.UserRole)
        filename = os.path.basename(first_path)

        # 1. Check for NMAP
        if filename.startswith("nmap_") or self.is_nmap_file(first_path):
            viewer = NmapViewer(first_path, self)
            viewer.show()
            return

        # 2. Check for Structured HTTPX
        if self.is_structured_httpx_file(first_path):
            self.open_selection_as_table(file_items)
            return

        # 3. Default to Log Viewer
        self.open_selection_as_log(file_items)

    def is_nmap_file(self, path):
        """Reads start of file to see if it looks like Nmap output."""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(512)
                if "Nmap scan report for" in head or "# Nmap" in head:
                    return True
        except: pass
        return False

    def is_structured_httpx_file(self, path):
        try:
            line_regex = re.compile(r"^https?://[^\s]+\s+\[\s*[\d,\s]+\s*\]\s+\[\s*\d+\s*\]")
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for _ in range(5):
                    line = f.readline()
                    if not line: break
                    clean = ansi_escape.sub('', line).strip()
                    if line_regex.match(clean): return True
        except: pass
        return False

    def open_selection_as_table(self, items):
        paths = [i.data(0, Qt.UserRole) for i in items]
        viewer = PlaygroundWindow(paths, self.terminal_widget, self.current_path, self)
        viewer.show()

    def open_selection_as_log(self, items):
        for item in items:
            path = item.data(0, Qt.UserRole)
            viewer = TerminalLogViewer(path, self)
            viewer.show()

    def open_context_menu(self, position):
        item = self.tree_widget.itemAt(position)
        if not item: return
        
        item_type = item.data(0, Qt.UserRole + 1)
        path = item.data(0, Qt.UserRole)

        menu = QMenu()
        if item_type == "dir":
            menu.addAction("Open Folder").triggered.connect(lambda: setattr(self, 'current_path', path) or self.refresh_playground())
            menu.addAction("Open Terminal Here").triggered.connect(lambda: self.open_system_terminal(path))
        elif item_type == "file":
            menu.addAction("Open in Nmap Viewer").triggered.connect(lambda: NmapViewer(path, self).show())
            menu.addAction("Open in Structured Viewer").triggered.connect(lambda: self.open_selection_as_table([item]))
            menu.addAction("Open in Log Viewer").triggered.connect(lambda: self.open_selection_as_log([item]))
        menu.exec_(self.tree_widget.viewport().mapToGlobal(position))

    def open_system_terminal(self, path):
        try:
            if sys.platform == 'win32': os.system(f'start cmd /K "cd /d {path}"')
            elif sys.platform == 'darwin': subprocess.run(['open', '-a', 'Terminal', path])
            else: subprocess.Popen(['x-terminal-emulator', '--working-directory', path])
        except: pass

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: self.font_size = min(30, self.font_size + 1)
            else: self.font_size = max(8, self.font_size - 1)
            font = self.tree_widget.font()
            font.setPointSize(self.font_size)
            self.tree_widget.setFont(font)
            icon_size = max(16, self.font_size + 12)
            self.tree_widget.setIconSize(QSize(icon_size, icon_size))
            event.accept()
        else:
            super().wheelEvent(event)
