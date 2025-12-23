import os
import re
import html
from urllib.parse import urlparse
from collections import Counter
import webbrowser
import subprocess

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QDialog,
    QTableView, QHeaderView, QMessageBox, QPushButton, QHBoxLayout,
    QTextEdit, QDialogButtonBox, QTabWidget, QListWidget, QLabel, QMenu,
    QStyleOption, QStyle, QLineEdit, QCheckBox, QApplication, QFrame
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import (
    QIcon, QStandardItemModel, QStandardItem, QColor, QBrush, 
    QPainter, QPixmap, QFont, QKeySequence
)

# --- Matplotlib Integration ---
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from utils import db as command_db
from .dialogs import FuzzerDialog

# ==========================================
#       NEW: Enhanced Terminal Log Viewer
# ==========================================

class TerminalLogViewer(QDialog):
    """
    A robust viewer for raw terminal output files.
    Features: ANSI color rendering, Search, Zooming, and Line wrapping.
    """
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Log Viewer - {os.path.basename(file_path)}")
        self.resize(1000, 700)
        
        # --- UI Setup ---
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find...")
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.setMaximumWidth(300)
        
        self.btn_next = QPushButton("↓")
        self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(self.find_next)
        
        self.btn_prev = QPushButton("↑")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(self.find_prev)
        
        self.check_wrap = QCheckBox("Word Wrap")
        self.check_wrap.setChecked(True)
        self.check_wrap.toggled.connect(self.toggle_wrap)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedWidth(30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedWidth(30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)

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
        
        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        # Set a monospaced font
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)
        
        # Dark theme for terminal feel
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1b2b42;  /* Light Navy Blue */
                color: #d8dee9;             /* Soft off-white */
                border: 2px solid #2e3440;
                selection-background-color: #4c566a;
                selection-color: #eceff4;
            }
        """)
        
        layout.addWidget(self.text_edit)
        
        layout.addWidget(self.text_edit)
        
        # Close Button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

        # Load Content
        self.load_file_content()

    def load_file_content(self):
        """Reads the file, converts ANSI codes to HTML, and displays it."""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                html_content = self.ansi_to_html(content)
                # Wrap in pre to preserve whitespace, using distinct font family
                self.text_edit.setHtml(f"<pre style='font-family: Consolas, monospace;'>{html_content}</pre>")
        except Exception as e:
            self.text_edit.setPlainText(f"Error reading file:\n{e}")

    def ansi_to_html(self, text):
        """
        Converts basic ANSI escape sequences to HTML spans for color.
        """
        # Escape HTML special characters first
        text = html.escape(text)

        # Map ANSI codes to hex colors
        ansi_colors = {
            '30': '#3b4252', '31': '#bf616a', '32': '#a3be8c', '33': '#ebcb8b',
            '34': '#81a1c1', '35': '#b48ead', '36': '#88c0d0', '37': '#e5e9f0',
            '90': '#4c566a', '91': '#d08770', '92': '#a3be8c', '93': '#ebcb8b',
            '94': '#5e81ac', '95': '#b48ead', '96': '#8fbcbb', '97': '#eceff4',
            '0': None,
        }

        # Regex to find ANSI codes: \x1b[...m
        pattern = re.compile(r'\x1b\[([\d;]+)m')
        
        parts = pattern.split(text)
        result = []
        current_span_open = False

        # The first part is always text before any code
        result.append(parts[0])

        for i in range(1, len(parts), 2):
            code_str = parts[i]
            text_chunk = parts[i+1]
            
            codes = code_str.split(';')
            color_code = None
            
            # Simple parser: just grab the last color code
            for c in codes:
                if c in ansi_colors:
                    if c == '0':
                        color_code = 'RESET'
                    else:
                        color_code = ansi_colors[c]

            if color_code == 'RESET':
                if current_span_open:
                    result.append("</span>")
                    current_span_open = False
            elif color_code:
                if current_span_open:
                    result.append("</span>")
                result.append(f"<span style='color:{color_code};'>")
                current_span_open = True
            
            result.append(text_chunk)
            
        if current_span_open:
            result.append("</span>")
            
        return "".join(result)

    def toggle_wrap(self, checked):
        if checked:
            self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        else:
            self.text_edit.setLineWrapMode(QTextEdit.NoWrap)

    def find_next(self):
        query = self.search_input.text()
        if not query: return
        self.text_edit.find(query)

    def find_prev(self):
        query = self.search_input.text()
        if not query: return
        self.text_edit.find(query, QTextEdit.FindBackward)

    def zoom_in(self):
        self.text_edit.zoomIn(1)

    def zoom_out(self):
        self.text_edit.zoomOut(1)

    def keyPressEvent(self, event):
        # Handle Zoom with Ctrl + / Ctrl -
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
                self.zoom_in()
                return
            elif event.key() == Qt.Key_Minus:
                self.zoom_out()
                return
            elif event.key() == Qt.Key_F:
                self.search_input.setFocus()
                return
        super().keyPressEvent(event)
        
    def wheelEvent(self, event):
        # Handle Zoom with Ctrl + Scroll
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

# ==========================================
#       Existing Classes (Unchanged Logic)
# ==========================================

class StatsChartCanvas(FigureCanvas):
    """A custom canvas for displaying matplotlib charts within a PyQt dialog."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        is_dark_theme = "dark" in parent.styleSheet().lower()

        if is_dark_theme:
            plt.style.use('dark_background')
            self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#2e3440')
            self.axes = self.fig.add_subplot(111, facecolor='#2e3440')
            self.axes.tick_params(axis='x', colors='white')
            self.axes.tick_params(axis='y', colors='white')
            self.axes.xaxis.label.set_color('white')
            self.axes.yaxis.label.set_color('white')
            self.axes.title.set_color('white')
        else:
            plt.style.use('default')
            self.fig = Figure(figsize=(width, height), dpi=dpi)
            self.axes = self.fig.add_subplot(111)

        super().__init__(self.fig)
        self.setParent(parent)

    def plot_histogram(self, data, title):
        self.axes.clear()
        self.axes.hist(data, bins=20, color='#88c0d0', edgecolor='#2e3440' if "dark" in self.parent().styleSheet().lower() else "white", linewidth=1.5)
        self.axes.set_title(title, fontsize=14, fontweight='bold')
        self.axes.set_xlabel("Value", fontsize=12)
        self.axes.set_ylabel("Frequency", fontsize=12)
        self.fig.tight_layout()
        self.draw()

    def plot_bar_chart(self, labels, values, title, xlabel='Count'):
        self.axes.clear()
        y_pos = range(len(labels))
        self.axes.barh(y_pos, values, align='center', color='#81a1c1', height=0.6)
        self.axes.set_yticks(y_pos)
        self.axes.set_yticklabels(labels, fontsize=9)
        self.axes.invert_yaxis()
        self.axes.set_xlabel(xlabel, fontsize=10)
        self.axes.set_title(title, fontsize=12, fontweight='bold')
        self.fig.tight_layout(rect=[0.1, 0, 0.9, 1])
        self.draw()

    def plot_pie_chart(self, labels, sizes, title):
        self.axes.clear()
        is_dark_theme = "dark" in self.parent().styleSheet().lower()
        colors = ['#5e81ac', '#bf616a', '#d08770', '#a3be8c', '#b48ead']
        textprops = {'color': 'white' if is_dark_theme else 'black'}
        self.axes.pie(sizes, labels=labels, autopct='%1.1f%%',
                      shadow=True, startangle=90, colors=colors, textprops=textprops)
        self.axes.axis('equal')
        self.axes.set_title(title, fontsize=12, fontweight='bold')
        self.fig.tight_layout()
        self.draw()

class StatisticsDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Dataset Statistics")
        self.setGeometry(200, 200, 800, 600)
        layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        text_stats_widget = QWidget()
        text_layout = QVBoxLayout(text_stats_widget)
        self.stats_text_edit = QTextEdit(readOnly=True)
        self.stats_text_edit.setFontFamily("Courier New")
        text_layout.addWidget(self.stats_text_edit)
        tab_widget.addTab(text_stats_widget, "Textual Report")
        
        charts_widget = QWidget()
        charts_layout = QHBoxLayout(charts_widget)
        self.column_list = QListWidget()
        self.column_list.setMaximumWidth(200)
        self.column_list.itemClicked.connect(self.update_chart)
        self.chart_canvas = StatsChartCanvas(parent=self)
        charts_layout.addWidget(self.column_list)
        charts_layout.addWidget(self.chart_canvas)
        tab_widget.addTab(charts_widget, "Charts")
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.calculate_and_display_text_stats()
        self.populate_chart_columns()

    def calculate_and_display_text_stats(self):
        stats_report = []
        for col in range(self.model.columnCount()):
            header = self.model.horizontalHeaderItem(col).text()
            if header == '⭐': continue

            stats_report.append(f"--- Statistics for Column: '{header}' ---\n")
            values = [self.model.item(row, col).text() for row in range(self.model.rowCount()) if self.model.item(row, col)]
            
            if not values:
                stats_report.append("No data in this column.\n\n")
                continue

            try:
                numeric_values = [float(v) for v in values]
                is_numeric = True
            except (ValueError, TypeError):
                is_numeric = False
            
            if is_numeric:
                count = len(numeric_values)
                mean = sum(numeric_values) / count
                median = sorted(numeric_values)[count // 2]
                std_dev = (sum((x - mean) ** 2 for x in numeric_values) / count) ** 0.5
                stats_report.extend([
                    f"  Type: Numeric",
                    f"  Count: {count}",
                    f"  Mean: {mean:.2f}",
                    f"  Median: {median}",
                    f"  Std Dev: {std_dev:.2f}",
                    f"  Min: {min(numeric_values)}",
                    f"  Max: {max(numeric_values)}\n"
                ])
            else:
                value_counts = Counter(values)
                stats_report.extend([
                    f"  Type: Textual",
                    f"  Total Rows: {len(values)}",
                    f"  Unique Values: {len(value_counts)}\n",
                    "  Most Common Values:"
                ])
                stats_report.extend([f"    - '{value}': {count} occurrences" for value, count in value_counts.most_common(15)])
                if len(value_counts) > 15:
                    stats_report.append("    - ...and more.\n")
            
            stats_report.append("\n")
        
        self.stats_text_edit.setText("\n".join(stats_report))

    def populate_chart_columns(self):
        self.column_list.clear()
        self.column_list.addItem("Status Code Distribution (Pie Chart)")
        
        for col in range(self.model.columnCount()):
            header = self.model.horizontalHeaderItem(col).text()
            if header in ['Status Code', 'Length', 'Technology', 'Title']:
                self.column_list.addItem(header)

    def update_chart(self, item):
        col_name = item.text()

        if col_name == "Status Code Distribution (Pie Chart)":
            status_codes = [int(self.model.item(row, 5).text()) for row in range(self.model.rowCount())]
            
            status_groups = {'2xx (Success)': 0, '3xx (Redirection)': 0, '4xx (Client Error)': 0, '5xx (Server Error)': 0, 'Other': 0}
            for code in status_codes:
                if 200 <= code < 300: status_groups['2xx (Success)'] += 1
                elif 300 <= code < 400: status_groups['3xx (Redirection)'] += 1
                elif 400 <= code < 500: status_groups['4xx (Client Error)'] += 1
                elif 500 <= code < 600: status_groups['5xx (Server Error)'] += 1
                else: status_groups['Other'] += 1
            
            labels = [k for k, v in status_groups.items() if v > 0]
            sizes = [v for k, v in status_groups.items() if v > 0]

            if labels:
                self.chart_canvas.plot_pie_chart(labels, sizes, "Status Code Distribution")
            return

        header_map = {self.model.horizontalHeaderItem(i).text(): i for i in range(self.model.columnCount())}
        col_index = header_map.get(col_name)
        
        if col_index is None: return

        values = [self.model.item(row, col_index).text() for row in range(self.model.rowCount())]

        if col_name == 'Length':
            numeric_values = sorted([(int(v), self.model.item(i, 2).text()) for i, v in enumerate(values) if v.isdigit()], reverse=True)
            if not numeric_values: return
            lengths, hosts = zip(*numeric_values)
            self.chart_canvas.plot_bar_chart(hosts, lengths, "Content Length by Host", xlabel="Length (bytes)")
        elif col_name in ['Technology', 'Title', 'Status Code']:
            counts = Counter(values)
            all_items = counts.most_common()
            if not all_items: return
            labels, data = zip(*all_items)
            self.chart_canvas.plot_bar_chart(labels, data, f"Distribution of {col_name}s")

class RiskAnalysisDialog(QDialog):
    def __init__(self, urls, parent=None):
        super().__init__(parent)
        self.urls = urls
        self.setWindowTitle("URL Risk Analysis")
        self.setGeometry(250, 250, 800, 700)
        self.HIGH_RISK_KEYWORDS = command_db.get_high_risk_keywords()
        self.INTERESTING_KEYWORDS = command_db.get_interesting_keywords()
        self.SENSITIVE_EXTENSIONS = [
            ".xls", ".xml", ".xlsx", ".json", ".pdf", ".sql", ".doc", ".docx", 
            ".pptx", ".txt", ".zip", ".tar.gz", ".tgz", ".bak", ".7z", ".rar", 
            ".log", ".cache", ".secret", ".db", ".backup", ".yml", ".gz", 
            ".config", ".csv", ".yaml", ".md", ".md5", ".tar", ".xz", ".7zip", 
            ".p12", ".pem", ".key", ".crt", ".csr", ".sh", ".pl", ".py", 
            ".java", ".class", ".jar", ".war", ".ear", ".sqlitedb", ".sqlite3", 
            ".dbf", ".db3", ".accdb", ".mdb", ".sqlcipher", ".gitignore", ".env", 
            ".ini", ".conf", ".properties", ".plist", ".cfg"
        ]
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>High Risk URLs</h2>"))
        self.high_risk_display = QTextEdit(readOnly=True)
        layout.addWidget(self.high_risk_display)
        layout.addWidget(QLabel("<h2>Potentially Interesting URLs</h2>"))
        self.interesting_display = QTextEdit(readOnly=True)
        layout.addWidget(self.interesting_display)
        layout.addWidget(QLabel("<h2>URLs with Sensitive Extensions</h2>"))
        self.sensitive_ext_display = QTextEdit(readOnly=True)
        layout.addWidget(self.sensitive_ext_display)
        close_button = QDialogButtonBox(QDialogButtonBox.Close)
        close_button.rejected.connect(self.reject)
        layout.addWidget(close_button)
        self.analyze_and_display_urls()

    def analyze_and_display_urls(self):
        high_risk_html = []
        interesting_html = []
        sensitive_ext_html = []
        for url in self.urls:
            is_high_risk = any(keyword in url.lower() for keyword in self.HIGH_RISK_KEYWORDS)
            is_interesting = any(keyword in url.lower() for keyword in self.INTERESTING_KEYWORDS)
            has_sensitive_ext = any(url.lower().endswith(ext) for ext in self.SENSITIVE_EXTENSIONS)
            if is_high_risk:
                high_risk_html.append(f'<span style="color: #bf616a;">{url}</span>')
            elif is_interesting:
                interesting_html.append(f'<span style="color: #ebcb8b;">{url}</span>')
            if has_sensitive_ext:
                sensitive_ext_html.append(f'<span style="color: #d08770;">{url}</span>')
        self.high_risk_display.setHtml("<br>".join(high_risk_html))
        self.interesting_display.setHtml("<br>".join(interesting_html))
        self.sensitive_ext_display.setHtml("<br>".join(sensitive_ext_html))

class NumericStandardItem(QStandardItem):
    def __lt__(self, other):
        try:
            return int(self.text()) < int(other.text())
        except ValueError:
            return self.text() < other.text()

class PlaygroundWindow(QDialog):
    """
    Structured Viewer for httpx/table data.
    """
    def __init__(self, file_paths, terminal_widget, working_directory, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.terminal_widget = terminal_widget
        self.working_directory = working_directory
        self.starred_hosts = set()
        self.starred_hosts_file = os.path.join(self.working_directory, "starred_hosts.txt")
        self.load_starred_hosts()       
        title = f"Structured Viewer - {os.path.basename(file_paths[0])}" if len(file_paths) == 1 else f"Structured Viewer - {len(file_paths)} files"
        self.setWindowTitle(title)
        self.setGeometry(150, 150, 1100, 700)

        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()
        self.risk_button = QPushButton("Analyze URL Risks")
        self.risk_button.clicked.connect(self.show_risk_analysis)
        top_bar_layout.addWidget(self.risk_button)
        top_bar_layout.addStretch()
        self.stats_button = QPushButton("View Stats")
        self.stats_button.clicked.connect(self.show_stats)
        top_bar_layout.addWidget(self.stats_button)
        main_layout.addLayout(top_bar_layout)
        
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)
        main_layout.addWidget(self.table_view)
        
        self.model = QStandardItemModel()
        self.model.itemChanged.connect(self.on_item_changed)
        
        # Load data, if it fails to find meaningful structured data, we can warn
        self.load_and_parse_data()

        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.open_context_menu)
        self.table_view.doubleClicked.connect(self.on_cell_double_clicked)

    def load_starred_hosts(self):
        if os.path.exists(self.starred_hosts_file):
            with open(self.starred_hosts_file, 'r') as f:
                self.starred_hosts = set(line.strip() for line in f)

    def save_starred_hosts(self):
        try:
            with open(self.starred_hosts_file, 'w') as f:
                for host in sorted(list(self.starred_hosts)):
                    f.write(host + '\n')
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save starred hosts: {e}")

    def on_item_changed(self, item):
        if item.column() == 0:
            row = item.row()
            host_item = self.model.item(row, 2)
            if host_item:
                host = host_item.text()
                if item.checkState() == Qt.Checked:
                    self.starred_hosts.add(host)
                else:
                    self.starred_hosts.discard(host)
                self.save_starred_hosts()

    def colorize_row(self, row, color_hex):
        for col in range(self.model.columnCount()):
            item = self.model.item(row, col)
            if item:
                if color_hex:
                    item.setBackground(QBrush(QColor(color_hex)))
                else:
                    item.setBackground(QBrush())

    def get_url_from_row(self, row):
        schema = self.model.item(row, 1).text()
        host = self.model.item(row, 2).text()
        path = self.model.item(row, 3).text() if self.model.item(row, 3) else ''
        return f"{schema}://{host}{path}"

    def colorize_status_code(self, item, status_code):
        if 200 <= status_code < 300: color = QColor("green")
        elif 300 <= status_code < 400: color = QColor("blue")
        elif 400 <= status_code < 500: color = QColor("orange")
        elif 500 <= status_code < 600: color = QColor("red")
        else: color = QColor("white")
        item.setForeground(color)

    def load_and_parse_data(self):
        self.all_records = [rec for fp in self.file_paths for rec in self.parse_httpx_file(fp)]
        if not self.all_records:
            # Not showing error here to allow hybrid usage, 
            # but ideally this window is only called for valid files.
            return

        headers = ['⭐', 'Schema', 'Host', 'Path', 'Extension', 'Status Code', 'Length', 'Technology']
        self.model.setHorizontalHeaderLabels(headers)

        for record in self.all_records:
            host = record.get('host', '')
            star_item = QStandardItem()
            star_item.setCheckable(True)
            if host in self.starred_hosts:
                star_item.setCheckState(Qt.Checked)
            
            status_code = int(record.get('status_code', 0))
            status_item = NumericStandardItem(f"{status_code:d}")
            self.colorize_status_code(status_item, status_code)
            
            row_items = [
                star_item,
                QStandardItem(str(record.get('schema', ''))),
                QStandardItem(host),
                QStandardItem(str(record.get('path', ''))),
                QStandardItem(str(record.get('extension', ''))),
                status_item,
                NumericStandardItem(f"{record.get('length', 0):d}"),
                QStandardItem(str(record.get('technology', '')))
            ]
            self.model.appendRow(row_items)

        self.table_view.setModel(self.model)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.setColumnWidth(0, 30)
    
    def on_cell_double_clicked(self, index):
        if index.column() == 2:
            self.open_in_browser(index.row())

    def open_context_menu(self, position):
        index = self.table_view.indexAt(position)
        if not index.isValid(): return
        row = index.row()
        menu = QMenu()
        colorize_menu = menu.addMenu("Colorize Row")
        colors = {"Red": "#bf616a", "Green": "#a3be8c", "Blue": "#81a1c1", "Yellow": "#ebcb8b", "None": None}
        for name, color_hex in colors.items():
            action = colorize_menu.addAction(name)
            action.triggered.connect(lambda checked, r=row, c=color_hex: self.colorize_row(r, c))

        if index.column() == 2:
            menu.addSeparator()
            open_browser_action = menu.addAction("Open in default browser")
            open_burp_action = menu.addAction("Open with Burp's Chromium")
            fuzz_action = menu.addAction("Fuzz with ffuf")
            action = menu.exec_(self.table_view.viewport().mapToGlobal(position))
            
            if action == open_browser_action: self.open_in_browser(row)
            elif action == open_burp_action: self.open_in_burp_browser(row)
            elif action == fuzz_action: self.open_fuzzer_dialog(row)
        else:
            menu.exec_(self.table_view.viewport().mapToGlobal(position))
            
    def open_in_browser(self, row):
        url = self.get_url_from_row(row)
        webbrowser.open_new_tab(url)
        
    def open_in_burp_browser(self, row):
        url = self.get_url_from_row(row)
        try:
            chromium_path = "/usr/bin/chromium" 
            subprocess.Popen([chromium_path, "--proxy-server=127.0.0.1:8080", "--ignore-certificate-errors", url])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not launch browser: {e}")

    def open_fuzzer_dialog(self, row):
        url = self.get_url_from_row(row)
        if not url.endswith('/'): url += '/'
        dialog = FuzzerDialog(url=url, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.command:
            self.terminal_widget.add_command_to_slot(dialog.command)

    def show_risk_analysis(self):
        if not hasattr(self, 'all_records') or not self.all_records:
            QMessageBox.information(self, "No Data", "There are no URLs to analyze.")
            return
        full_urls = [f"{rec.get('schema', '')}://{rec.get('host', '')}{rec.get('path', '')}" for rec in self.all_records]
        dialog = RiskAnalysisDialog(full_urls, self)
        dialog.exec_()

    def parse_httpx_file(self, file_path):
        records = []
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        line_regex = re.compile(
            r"^(?P<url>https?://[^\s]+)\s+"
            r"\[\s*(?P<status_code>[\d,\s]+)\s*\]\s+"
            r"\[\s*(?P<length>\d+)\s*\]\s+"
            r"(?:\[\s*(?P<technology>[^\]]+)\s*\])?"
        )
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    clean_line = ansi_escape.sub('', line).strip()
                    match = line_regex.match(clean_line)
                    if not match: continue
                    data = match.groupdict()
                    parsed_url = urlparse(data['url'])
                    final_status_code = data['status_code'].split(',')[-1].strip()
                    _, extension = os.path.splitext(parsed_url.path)
                    records.append({
                        'schema': parsed_url.scheme, 'host': parsed_url.hostname, 'path': parsed_url.path,
                        'extension': extension if extension else 'N/A', 'status_code': int(final_status_code),
                        'length': int(data['length']), 'technology': data.get('technology', 'N/A').strip()
                    })
        except Exception:
            pass # Fail silently so we don't break on non-httpx files
        return records

    def show_stats(self):
        if self.model.rowCount() == 0:
            QMessageBox.information(self, "No Data", "There is no data to analyze.")
            return
        dialog = StatisticsDialog(self.model, self)
        dialog.exec_()

# ==========================================
#       Updated: PlaygroundTabWidget
# ==========================================

class PlaygroundTabWidget(QWidget):
    """
    The main widget for the 'Playground' tab.
    Added Features: Zooming with Ctrl+Scroll, Enhanced File Opening.
    """
    def __init__(self, working_directory, icon_path, terminal_widget, hostname_test=False, parent=None):
        super().__init__(parent)
        self.working_directory = working_directory
        self.icon_path = icon_path
        self.terminal_widget = terminal_widget
        
        # Zoom state
        self.font_size = 20
        
        # Background Setup
        self.bg_pixmap = None
        if hostname_test:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            bg_path = os.path.join(base_path, "themes", "img", "pokemon", "playground_bg.png")
            if os.path.exists(bg_path):
                self.bg_pixmap = QPixmap(bg_path)

        layout = QVBoxLayout(self)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.itemDoubleClicked.connect(self.open_smart)

        font = self.tree_widget.font()
        font.setPointSize(self.font_size)
        self.tree_widget.setFont(font)
        
        icon_size = self.font_size + 8
        self.tree_widget.setIconSize(QSize(icon_size, icon_size))
        
        # Context menu for "Open As..."
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.open_context_menu)

        if self.bg_pixmap:
            self.tree_widget.setStyleSheet("""
                QTreeWidget { background-color: transparent; }
                QTreeWidget::item { color: #ffffff; } 
                QHeaderView::section { background-color: transparent; }
            """)
            
        layout.addWidget(self.tree_widget)
        
        # Button bar
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_playground)
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self.open_smart)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(open_btn)
        layout.addLayout(btn_layout)
        
        self.refresh_playground()

    def wheelEvent(self, event):
        """Handle Zoom In/Out with Ctrl + Wheel on the tree widget area."""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.font_size += 1
            else:
                self.font_size = max(6, self.font_size - 1)
            
            # Apply new font size to tree items
            font = self.tree_widget.font()
            font.setPointSize(self.font_size)
            self.tree_widget.setFont(font)
            
            # Resize icons slightly to match text
            icon_size = max(16, self.font_size + 6)
            self.tree_widget.setIconSize(QSize(icon_size, icon_size))
            event.accept()
        else:
            super().wheelEvent(event)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        if self.bg_pixmap and not self.bg_pixmap.isNull():
            p.drawPixmap(self.rect(), self.bg_pixmap)
        else:
            self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def open_context_menu(self, position):
        item = self.tree_widget.itemAt(position)
        if not item: return
        
        menu = QMenu()
        open_table_action = menu.addAction("Open in Structured Viewer (Table)")
        open_log_action = menu.addAction("Open in Log Viewer (Text)")
        
        action = menu.exec_(self.tree_widget.viewport().mapToGlobal(position))
        
        if action == open_table_action:
            self.open_selection_as_table()
        elif action == open_log_action:
            self.open_selection_as_log()

    def open_smart(self):
        """
        Decides whether to open as a Table (if it looks like structured data) 
        or as a Log (default).
        """
        selected_items = self.tree_widget.selectedItems()
        if not selected_items: return
        
        # Grab the first file to test content
        path = selected_items[0].data(0, Qt.UserRole)
        if not path or not os.path.isfile(path): return

        if self.is_structured_httpx_file(path):
            self.open_selection_as_table()
        else:
            self.open_selection_as_log()

    def is_structured_httpx_file(self, path):
        """Checks if the first few lines of a file match the httpx regex."""
        try:
            line_regex = re.compile(
                r"^https?://[^\s]+\s+\[\s*[\d,\s]+\s*\]\s+\[\s*\d+\s*\]"
            )
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for _ in range(5): # Check first 5 lines
                    line = f.readline()
                    if not line: break
                    clean = ansi_escape.sub('', line).strip()
                    if line_regex.match(clean):
                        return True
        except:
            pass
        return False

    def open_selection_as_table(self):
        selected_items = self.tree_widget.selectedItems()
        file_paths = [item.data(0, Qt.UserRole) for item in selected_items if item.data(0, Qt.UserRole) and os.path.isfile(item.data(0, Qt.UserRole))]
        
        if not file_paths: return
        
        # Check if actually parsable
        valid_files = [fp for fp in file_paths if self.is_structured_httpx_file(fp)]
        
        if not valid_files:
             QMessageBox.warning(self, "Format Error", "Selected file(s) do not appear to be structured httpx output.\nOpening in Log Viewer instead.")
             self.open_selection_as_log()
             return

        viewer = PlaygroundWindow(valid_files, self.terminal_widget, self.working_directory, self)
        viewer.exec_()

    def open_selection_as_log(self):
        selected_items = self.tree_widget.selectedItems()
        file_paths = [item.data(0, Qt.UserRole) for item in selected_items if item.data(0, Qt.UserRole) and os.path.isfile(item.data(0, Qt.UserRole))]
        
        if not file_paths: return

        # Open a separate window for each file if multiple are selected
        for fp in file_paths:
            viewer = TerminalLogViewer(fp, self)
            viewer.show() # Use show() instead of exec_() so we can open multiple at once

    def set_working_directory(self, path):
        self.working_directory = path
        self.refresh_playground()

    def refresh_playground(self):
        self.tree_widget.clear()
        folder_icon = QIcon(os.path.join(self.icon_path, "folder.svg"))
        file_icon = QIcon(os.path.join(self.icon_path, "file.svg"))
        bag_icon = QIcon(os.path.join(self.icon_path, "bag.svg"))

        bags = {}
        try:
            for item_name in sorted(os.listdir(self.working_directory)):
                full_path = os.path.join(self.working_directory, item_name)
                if os.path.isdir(full_path):
                    dir_item = QTreeWidgetItem(self.tree_widget, [item_name])
                    dir_item.setIcon(0, folder_icon)
                    dir_item.setData(0, Qt.UserRole, full_path)
                elif "_" in item_name:
                    prefix = item_name.split('_')[0]
                    if prefix not in bags:
                        bags[prefix] = QTreeWidgetItem(self.tree_widget, [prefix])
                        bags[prefix].setIcon(0, bag_icon)
                    file_item = QTreeWidgetItem(bags[prefix], [item_name])
                    file_item.setIcon(0, file_icon)
                    file_item.setData(0, Qt.UserRole, full_path)
                else:
                    file_item = QTreeWidgetItem(self.tree_widget, [item_name])
                    file_item.setIcon(0, file_icon)
                    file_item.setData(0, Qt.UserRole, full_path)
            self.tree_widget.expandAll()
        except Exception as e:
            QTreeWidgetItem(self.tree_widget, [f"Error: {e}"])