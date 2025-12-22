import sys
import os
import requests as r
from bs4 import BeautifulSoup
import urllib3
import subprocess
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
                             QRadioButton, QCheckBox, QProgressBar, QFrame,
                             QFormLayout, QAbstractItemView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QColor, QBrush, QDesktopServices

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 1. SNYK WORKER (Web Scraper)
# ---------------------------------------------------------
class SnykScraperWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, version):
        super().__init__()
        self.url = url
        self.version = version

    def normalize_version(self, version):
        parts = version.split(".")
        while len(parts) < 3:
            parts.append("0")
        return ".".join(parts[:3])

    def check_for_recursion(self, constraint):
        return constraint.count("<") + constraint.count(">")

    def find_first_matched(self, target_chars, string):
        target_chars.sort(key=lambda x: -len(x))
        matches = ((char, string.find(char)) for char in target_chars if string.find(char) != -1)
        first_match = min(matches, key=lambda x: x[1], default=(None, -1))
        return first_match[0]

    def version_extractor(self, constraint, start_character):
        start = constraint.find(start_character) + 1
        end = min(
            (constraint.find(op, start) for op in ("<", ">") if constraint.find(op, start) != -1),
            default=len(constraint)
        )
        version = constraint[start:end].strip()
        version = version.replace("=", "").replace("-beta", "")
        return version

    def parse_global_constraints(self, constraints):
        global_parsed = []
        for constraint in constraints.split(","):
            constraint = constraint.strip()
            local_parsed = []
            rounds = self.check_for_recursion(constraint)
            target_chars = ["<", ">", "<=", ">="]
            for _ in range(rounds):
                result = self.find_first_matched(target_chars, constraint)
                if result:
                    comparator = result
                    version = self.version_extractor(constraint, comparator)
                    remove = f"{comparator}{version}"
                    local_parsed.append((comparator, self.normalize_version(version)))
                    constraint = constraint.replace(remove, "", 1)
            global_parsed.append(local_parsed)
        return global_parsed

    def is_version_allowed(self, target_version, constraints):
        global_result = True
        for constraint in constraints:
            local_result = True
            for comparator, constraint_version in constraint:
                try:
                    if comparator == "<" and not target_version < constraint_version: local_result = False
                    elif comparator == ">" and not target_version > constraint_version: local_result = False
                    elif comparator == "<=" and not target_version <= constraint_version: local_result = False
                    elif comparator == ">=" and not target_version >= constraint_version: local_result = False
                except: local_result = False
            if not local_result: global_result = False
        return global_result

    def check_vulnerabilities(self, target_version, constraints_string):
        try:
            constraints = self.parse_global_constraints(constraints_string)
            target_version = self.normalize_version(target_version)
            return self.is_version_allowed(target_version, constraints)
        except: return False

    def run(self):
        try:
            norm_version = self.normalize_version(self.version)
            global_data = []
            response = r.get(url=self.url, verify=False, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table')
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if not cells: continue

                        # --- IMPROVED PARSING LOGIC ---
                        
                        # 1. Vulnerability Name & Link (Inside <a> tag in 1st cell)
                        a_tag = cells[0].find("a")
                        if a_tag:
                            vuln_name = a_tag.text.strip()
                            vuln_link = "https://security.snyk.io" + a_tag["href"] if a_tag.has_attr("href") else "N/A"
                        else:
                            vuln_name = cells[0].text.strip()
                            vuln_link = "N/A"

                        # 2. Severity (Clean Extraction)
                        # Attempt to find specific class (e.g., 'severity-high')
                        severity = "Unknown"
                        sev_span = cells[0].find("span") # Snyk usually wraps sev in a span
                        if sev_span and "class" in sev_span.attrs:
                            classes = sev_span["class"]
                            # Convert class to readable string
                            for c in classes:
                                if "critical" in c.lower(): severity = "Critical"
                                elif "high" in c.lower(): severity = "High"
                                elif "medium" in c.lower(): severity = "Medium"
                                elif "low" in c.lower(): severity = "Low"
                        
                        # Fallback: Parse first letter of text if class extraction failed
                        if severity == "Unknown":
                            full_text = cells[0].text.strip()
                            if full_text.startswith("C") and "Critical" not in vuln_name: severity = "Critical"
                            elif full_text.startswith("H") and "High" not in vuln_name: severity = "High"
                            elif full_text.startswith("M") and "Medium" not in vuln_name: severity = "Medium"
                            elif full_text.startswith("L") and "Low" not in vuln_name: severity = "Low"

                        # 3. Constraints (Usually in 2nd cell)
                        constraints_string = ""
                        if len(cells) > 1:
                            constraints_string = cells[1].text.strip()

                        # --- CHECK & APPEND ---
                        if self.check_vulnerabilities(norm_version, constraints_string):
                            ui_row = [
                                severity,
                                vuln_name,
                                constraints_string,
                                vuln_link
                            ]
                            global_data.append(ui_row)

            self.results_ready.emit(global_data)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ---------------------------------------------------------
# 2. CVEMAP WORKER (ProjectDiscovery CLI)
# ---------------------------------------------------------
class CveMapWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, flags):
        super().__init__()
        self.flags = flags 

    def run(self):
        from shutil import which
        
        tool_path = which("cvemap")
        
        if tool_path is None:
            home = os.path.expanduser("~")
            go_path = os.path.join(home, "go", "bin", "cvemap")
            if os.path.exists(go_path):
                tool_path = go_path
            else:
                self.error_occurred.emit("Error: 'cvemap' not found.\nPlease ensure it is installed and in your PATH.")
                return

        try:
            # Construct command
            cmd = [tool_path] + self.flags + ["-json", "-silent"]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()

            data_list = []
            
            # ATTEMPT A: JSON Array
            if stdout.strip().startswith("["):
                try:
                    data_list = json.loads(stdout)
                except json.JSONDecodeError:
                    pass
            
            # ATTEMPT B: NDJSON (Line-by-line)
            if not data_list:
                for line in stdout.splitlines():
                    if not line.strip(): continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            data_list.append(obj)
                    except json.JSONDecodeError:
                        continue

            if not data_list:
                if process.returncode != 0:
                    self.error_occurred.emit(f"CVEMap failed (Code {process.returncode}):\n{stderr}")
                else:
                    self.results_ready.emit([])
                return

            # Extract Fields
            results = []
            for d in data_list:
                if not isinstance(d, dict): continue

                cve_id = d.get("cve_id", "N/A")
                
                cvss = d.get("cvss_score", 0.0)
                cvss_str = f"{cvss:.1f}" if isinstance(cvss, (float, int)) else str(cvss)
                
                severity = d.get("severity", "unknown").upper()
                
                epss = d.get("epss_score", 0.0)
                epss_str = f"{epss:.5f}" if isinstance(epss, (float, int)) else str(epss)
                
                prod_raw = d.get("product", "-")
                if isinstance(prod_raw, list):
                    product = ", ".join(prod_raw[:2]) 
                else:
                    product = str(prod_raw)
                    
                age = d.get("age_in_days", d.get("age", ""))
                age_str = str(age) if age is not None else ""
                
                has_template = d.get("is_template", d.get("has_template", False))
                template_icon = "✅" if has_template else "❌"
                
                link = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

                results.append([cve_id, cvss_str, severity, epss_str, product, age_str, template_icon, link])

            self.results_ready.emit(results)

        except Exception as e:
            self.error_occurred.emit(f"Execution Error: {str(e)}")


# ---------------------------------------------------------
# 3. MAIN WIDGET
# ---------------------------------------------------------
class CVESearchWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.setup_ui()
        self.setup_styles()

    def setup_styles(self):
        # Comprehensive Dark Theme Styles
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2f;
                color: #e0e0e0;
                font-family: 'Arial';
                font-size: 14px;
            }
            QGroupBox {
                border: 1px solid #4a4a5e;
                border-radius: 5px;
                margin-top: 10px;
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
            QLabel {
                color: #e0e0e0;
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
            QCheckBox, QRadioButton {
                color: #e0e0e0;
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
                background-color: #2f2f40;
                border: 1px solid #4a4a5e;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #00d2ff;
                border: 1px solid #00d2ff;
            }
            QPushButton { 
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d2ff, stop:1 #3a7bd5);
                color: white; 
                font-weight: bold; 
                border-radius: 6px; 
                padding: 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a7bd5, stop:1 #00d2ff);
            }
            QPushButton:pressed {
                background-color: #2a6bb5;
            }
            QPushButton:disabled {
                background-color: #4a4a5e;
                color: #888888;
            }
            
            /* --- FIXED TABLE STYLES --- */
            QTableWidget {
                background-color: #1e1e2f;
                alternate-background-color: #27273a;
                gridline-color: #444444;
                color: #e0e0e0;
                border: 1px solid #4a4a5e;
                selection-background-color: #3a7bd5;
                selection-color: white;
                outline: none;
            }
            QTableWidget::item {
                padding: 5px;
                color: #e0e0e0;
                border-bottom: 1px solid #2f2f40;
            }
            QTableWidget::item:selected {
                background-color: #3a7bd5;
                color: white;
            }
            QHeaderView::section {
                background-color: #2f2f40;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #444444;
                font-weight: bold;
            }
            /* Corner Button (Top Left) */
            QTableWidget QTableCornerButton::section {
                background-color: #2f2f40;
                border: 1px solid #444444;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                background: #1e1e2f;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background: #4a4a5e;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Header ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #2f2f40; border-radius: 8px; padding: 10px;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 5, 10, 5)
        
        lbl_icon = QLabel("📋")
        lbl_icon.setFont(QFont("Arial", 24))
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        
        lbl_title = QLabel("Vulnerability Intelligence")
        lbl_title.setFont(QFont("Arial", 18, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff; background: transparent; border: none;")
        
        h_layout.addWidget(lbl_icon)
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        main_layout.addWidget(header_frame)

        # --- Engine Selector ---
        engine_group = QGroupBox("1. Select Engine")
        e_layout = QHBoxLayout(engine_group)
        e_layout.setSpacing(20)
        
        self.radio_snyk = QRadioButton("Snyk Scraper")
        self.radio_snyk.setToolTip("Checks specific package versions against Snyk DB.")
        self.radio_snyk.setChecked(True)
        
        self.radio_cvemap = QRadioButton("CVEMap (ProjectDiscovery)")
        self.radio_cvemap.setToolTip("Queries CVE database for products, vendors, and exploitability.\nREQUIRES API KEY: cvemap -auth")
        
        self.radio_snyk.toggled.connect(self.update_ui_state)
        self.radio_cvemap.toggled.connect(self.update_ui_state)
        
        e_layout.addWidget(self.radio_snyk)
        e_layout.addWidget(self.radio_cvemap)
        e_layout.addStretch()
        main_layout.addWidget(engine_group)

        # --- Dynamic Input Area ---
        self.input_area = QGroupBox("2. Search Parameters")
        self.input_layout = QVBoxLayout(self.input_area)
        main_layout.addWidget(self.input_area)

        # Stack Containers
        self.container_snyk = QWidget()
        self.setup_snyk_ui()
        self.input_layout.addWidget(self.container_snyk)

        self.container_cvemap = QWidget()
        self.setup_cvemap_ui()
        self.input_layout.addWidget(self.container_cvemap)

        # --- Search Button ---
        self.btn_search = QPushButton("🚀 Run Analysis")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self.start_scan)
        main_layout.addWidget(self.btn_search)

        # --- Progress Bar ---
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar { 
                border: 1px solid #4a4a5e; 
                border-radius: 5px; 
                text-align: center; 
                color: white; 
                background-color: #2f2f40;
            } 
            QProgressBar::chunk { background-color: #00d2ff; }
        """)
        self.progress.setRange(0, 0) 
        self.progress.hide()
        main_layout.addWidget(self.progress)

        # --- Results Table ---
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Handle link clicks
        self.table.cellClicked.connect(self.open_link)
        main_layout.addWidget(self.table)

        # Initialize View
        self.update_ui_state()

    # --- UI LAYOUTS ---
    def setup_snyk_ui(self):
        layout = QFormLayout(self.container_snyk)
        layout.setLabelAlignment(Qt.AlignRight)
        
        self.inp_snyk_url = QLineEdit()
        self.inp_snyk_url.setPlaceholderText("https://security.snyk.io/package/composer/moodle%2Fmoodle")
        
        self.inp_snyk_ver = QLineEdit()
        self.inp_snyk_ver.setPlaceholderText("e.g. 3.7.0")
        
        lbl_url = QLabel("Package URL:")
        lbl_ver = QLabel("Target Version:")
        
        layout.addRow(lbl_url, self.inp_snyk_url)
        layout.addRow(lbl_ver, self.inp_snyk_ver)

    def setup_cvemap_ui(self):
        from PyQt5.QtWidgets import QGridLayout
        layout = QVBoxLayout(self.container_cvemap)
        
        # Grid for Parameters
        grid = QGridLayout()
        grid.setSpacing(10)

        # Row 0
        self.inp_cve_prod = QLineEdit()
        self.inp_cve_prod.setPlaceholderText("e.g. chrome")
        grid.addWidget(QLabel("Product:"), 0, 0)
        grid.addWidget(self.inp_cve_prod, 0, 1)

        self.inp_cve_vendor = QLineEdit()
        self.inp_cve_vendor.setPlaceholderText("e.g. google")
        grid.addWidget(QLabel("Vendor:"), 0, 2)
        grid.addWidget(self.inp_cve_vendor, 0, 3)

        # Row 1
        self.inp_cve_id = QLineEdit()
        self.inp_cve_id.setPlaceholderText("e.g. CVE-2025-XXXX")
        grid.addWidget(QLabel("CVE ID (Optional):"), 1, 0)
        grid.addWidget(self.inp_cve_id, 1, 1)

        self.combo_severity = QComboBox()
        self.combo_severity.addItems(["All", "critical", "high", "medium", "low", "unknown"])
        grid.addWidget(QLabel("Severity:"), 1, 2)
        grid.addWidget(self.combo_severity, 1, 3)

        layout.addLayout(grid)

        # Toggles
        toggles_layout = QHBoxLayout()
        self.chk_exploited = QCheckBox("Known Exploited (KEV)")
        self.chk_template = QCheckBox("Has Template (Nuclei)")
        self.chk_poc = QCheckBox("Has PoC")
        
        toggles_layout.addWidget(self.chk_exploited)
        toggles_layout.addWidget(self.chk_template)
        toggles_layout.addWidget(self.chk_poc)
        toggles_layout.addStretch()
        layout.addLayout(toggles_layout)

        # Advanced
        layout.addSpacing(5)
        raw_layout = QHBoxLayout()
        raw_lbl = QLabel("Raw Query:")
        raw_lbl.setToolTip("Advanced cvemap query syntax (e.g. 'product:chrome age:<30')")
        self.inp_cve_raw = QLineEdit()
        self.inp_cve_raw.setPlaceholderText("Overrides fields above (e.g. product:chrome age:<30)")
        self.inp_cve_raw.setStyleSheet("border: 1px dashed #4a4a5e; color: #aaaaaa;")
        
        raw_layout.addWidget(raw_lbl)
        raw_layout.addWidget(self.inp_cve_raw)
        layout.addLayout(raw_layout)

    def update_ui_state(self):
        is_snyk = self.radio_snyk.isChecked()
        self.container_snyk.setVisible(is_snyk)
        self.container_cvemap.setVisible(not is_snyk)

        self.table.setRowCount(0)
        
        if is_snyk:
            # Snyk Output Style
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["Severity", "Vulnerability", "Constraint", "Link"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        else:
            # CVEMap Output Style
            self.table.setColumnCount(8)
            headers = ["ID", "CVSS", "SEVERITY", "EPSS", "PRODUCT", "AGE", "TEMPLATE", "Link"]
            self.table.setHorizontalHeaderLabels(headers)
            
            h = self.table.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Interactive)
            h.setSectionResizeMode(7, QHeaderView.Stretch) # Link stretches
            
            self.table.setColumnWidth(0, 130) # ID
            self.table.setColumnWidth(1, 60)  # CVSS
            self.table.setColumnWidth(2, 90)  # Severity
            self.table.setColumnWidth(3, 80)  # EPSS
            self.table.setColumnWidth(4, 120) # Product
            self.table.setColumnWidth(5, 60)  # Age
            self.table.setColumnWidth(6, 80)  # Template

    # --- LOGIC ---
    def start_scan(self):
        self.table.setRowCount(0)
        self.progress.show()
        self.btn_search.setEnabled(False)

        if self.radio_snyk.isChecked():
            url = self.inp_snyk_url.text().strip()
            ver = self.inp_snyk_ver.text().strip()
            
            if not url or not ver:
                QMessageBox.warning(self, "Missing Input", "Please provide both the Snyk Package URL and the Target Version.")
                self.reset_ui()
                return

            self.worker = SnykScraperWorker(url, ver)
        
        else:
            # Prepare CVEMap Flags
            flags = []
            
            # Raw Query Check
            raw = self.inp_cve_raw.text().strip()
            if raw:
                # User manually wrote query
                flags.extend(["-q", raw])
            else:
                if self.inp_cve_prod.text().strip():
                    flags.extend(["-product", self.inp_cve_prod.text().strip()])
                
                if self.inp_cve_vendor.text().strip():
                    flags.extend(["-vendor", self.inp_cve_vendor.text().strip()])
                    
                if self.inp_cve_id.text().strip():
                    flags.extend(["-id", self.inp_cve_id.text().strip()])
                
                sev = self.combo_severity.currentText()
                if sev != "All":
                    flags.extend(["-severity", sev])
                
                # FLAGS
                if self.chk_exploited.isChecked(): flags.append("-kev")
                if self.chk_template.isChecked(): flags.append("-template")
                if self.chk_poc.isChecked(): flags.append("-poc")

                # Default limit
                flags.extend(["-limit", "50"])

            self.worker = CveMapWorker(flags)

        self.worker.results_ready.connect(self.display_results)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.finished.connect(self.reset_ui)
        self.worker.start()

    def display_results(self, data):
        self.table.setRowCount(len(data))
        for i, row_data in enumerate(data):
            for j, item in enumerate(row_data):
                item_text = str(item)
                table_item = QTableWidgetItem(item_text)
                
                # Force dark theme text color
                table_item.setForeground(QBrush(QColor("#e0e0e0")))
                
                self.table.setItem(i, j, table_item)
                
                # COLOR CODING FOR SEVERITY
                sev_idx = 0 if self.radio_snyk.isChecked() else 2
                link_idx = 3 if self.radio_snyk.isChecked() else 7
                
                if j == sev_idx:
                    val = item_text.lower()
                    color = None
                    if "critical" in val: color = QColor("#ff4444")
                    elif "high" in val: color = QColor("#ff8800")
                    elif "medium" in val: color = QColor("#ffcc00")
                    elif "low" in val: color = QColor("#00cc44")
                    
                    if color:
                        table_item.setForeground(QBrush(color))
                        table_item.setFont(QFont("Arial", 10, QFont.Bold))
                
                # STYLE CLICKABLE LINKS
                if j == link_idx:
                    if item_text.startswith("http"):
                        table_item.setForeground(QBrush(QColor("#3399ff")))
                        font = QFont("Arial", 10)
                        font.setUnderline(True)
                        table_item.setFont(font)
                        table_item.setToolTip("Click to open in browser")

        if len(data) == 0:
            QMessageBox.information(self, "No Results", "No vulnerabilities found matching criteria.")

    def open_link(self, row, col):
        """Handle clicks on the Link column to open URL in browser."""
        # Determine Link Column Index
        if self.radio_snyk.isChecked():
            link_col = 3
        else:
            link_col = 7
            
        if col == link_col:
            item = self.table.item(row, col)
            if item:
                url_str = item.text()
                if url_str.startswith("http"):
                    QDesktopServices.openUrl(QUrl(url_str))

    def show_error(self, err_msg):
        QMessageBox.critical(self, "Error", err_msg)

    def reset_ui(self):
        self.progress.hide()
        self.btn_search.setEnabled(True)