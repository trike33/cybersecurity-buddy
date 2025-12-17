import os
import shutil
import markdown
import re
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox,
    QLineEdit, QTextEdit, QPushButton, QApplication, QMessageBox, QFileDialog,
    QDialog, QTextBrowser, QListWidget, QListWidgetItem, QToolButton, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QTextCursor, QTextDocument
from PyQt5.QtPrintSupport import QPrinter
from utils import db as command_db
from modules.dialogs import TemplateEditorDialog

# --- Helper: Style Generator ---
def get_report_style(pdf_mode=False):
    """
    Returns the CSS string for the report.
    """
    if pdf_mode:
        # PDF Mode: Fixed widths, smaller fonts, zero margins on top of headers to avoid blank pages
        img_css = "width: 700px; display: block;" 
        body_font_size = "12pt"
        header_margin = "0"
        header_padding = "10px"
    else:
        # Screen Mode: Responsive
        img_css = "max-width: 100%; height: auto; object-fit: contain;"
        body_font_size = "14px"
        header_margin = "20px"
        header_padding = "5px"

    return f"""
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.4; font-size: {body_font_size}; margin: 0; padding: 0; }}
        
        /* Typography */
        /* IMPORTANT: margin-top: 0 is critical for PDF to avoid pushing headers to a new blank page */
        h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: {header_margin}; padding-top: {header_padding}; font-size: 22pt; font-weight: bold; }}
        h2 {{ color: #e67e22; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: {header_margin}; padding-top: {header_padding}; font-size: 16pt; font-weight: bold; }}
        h3 {{ color: #34495e; font-size: 14pt; margin-top: 15px; font-weight: bold; }}
        
        /* Content Spacing - Reduced to prevent large gaps */
        p, li {{ margin-bottom: 8px; text-align: justify; }}
        ul, ol {{ margin-top: 5px; margin-bottom: 10px; }}
        
        /* Code & Preformatted */
        code {{ background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-family: 'Courier New', monospace; color: #c7254e; font-size: 0.9em; }}
        pre {{ background-color: #2b2b2b; color: #f8f8f2; padding: 10px; border-radius: 5px; margin: 10px 0; white-space: pre-wrap; page-break-inside: avoid; }}
        pre code {{ background-color: transparent; color: #f8f8f2; }}
        
        /* Tables */
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; page-break-inside: avoid; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        
        /* Images */
        img {{ {img_css} margin: 10px auto; border: 1px solid #ccc; }}
        
        /* Sections & Layout */
        blockquote {{ border-left: 5px solid #eee; padding-left: 15px; color: #666; font-style: italic; margin: 10px 0; }}
        
        /* Page Break Handling */
        hr.page-break {{ page-break-after: always; visibility: hidden; margin: 0; padding: 0; height: 1px; border: none; }}
        
        /* Title Page Specifics */
        .title-container {{ width: 100%; text-align: center; padding-top: 200px; }}
        .title-main {{ font-size: 36pt; font-weight: bold; color: #2c3e50; margin-bottom: 20px; }}
        .title-sub {{ font-size: 18pt; color: #7f8c8d; margin-top: 20px; }}
        .title-meta {{ margin-top: 100px; font-size: 14pt; color: #333; }}
        
        /* Table of Contents */
        .toc-item {{ font-size: 14pt; margin-bottom: 8px; border-bottom: 1px dotted #ccc; padding: 5px; display: block; }}
    </style>
    """

# --- Helper: Body Renderer ---
def render_markdown_body(markdown_text, project_folder, pdf_mode=False):
    """
    Converts markdown to HTML body content ONLY (no <html> wrapper).
    """
    # Convert Markdown to HTML
    html_body = markdown.markdown(markdown_text, extensions=['fenced_code', 'tables'])
    
    # Fix Image Paths
    if project_folder:
        reports_img_dir = os.path.join(project_folder, "reports", "images")
        base_url = QUrl.fromLocalFile(reports_img_dir).toString()
        html_body = html_body.replace('src="images/', f'src="{base_url}/')

    # PDF Specific Image Scaling Fixes
    if pdf_mode:
        # 1. Strip existing dimensions
        html_body = re.sub(r'(<img[^>]+)(width|height)=["\'][^"\']*["\']', r'\1', html_body)
        # 2. Inject forced width for A4
        html_body = re.sub(r'<img([^>]+)>', r'<img\1 width="700">', html_body)

    return html_body

class ReportPreviewDialog(QDialog):
    def __init__(self, markdown_content, project_folder=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Report Preview")
        self.resize(1200, 900)
        
        layout = QVBoxLayout(self)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self.handle_links)
        self.browser.setStyleSheet("background-color: #1e1e2f; border: none;")
        
        layout.addWidget(self.browser)
        
        # 1. Get Style
        style = get_report_style(pdf_mode=False)
        
        # 2. Get Body
        body_html = render_markdown_body(markdown_content, project_folder, pdf_mode=False)
        
        # 3. Apply Dark Mode Override for Preview Window
        dark_override = """
        <style>
            body { background-color: #1e1e2f; color: #e0e0e0; }
            p, li, ul, ol, td, th, span, div { color: #e0e0e0 !important; }
            h1 { color: #4db6ac; border-bottom: 2px solid #4db6ac; }
            h2 { color: #ffca28; border-bottom: 1px solid #555; }
            h3 { color: #64b5f6; }
            table { border-color: #444; }
            th, td { border: 1px solid #444; }
            th { background-color: #2f2f40; color: #ffffff !important; }
            code { background-color: #383850; color: #ff80ab; }
            pre { background-color: #12121a; border: 1px solid #333; }
            img { background-color: #e0e0e0; border: 1px solid #555; }
            blockquote { border-left: 5px solid #444; color: #aaa !important; }
            a { color: #82b1ff; }
        </style>
        """
        
        full_html = f"<html><head>{style}{dark_override}</head><body>{body_html}</body></html>"
        self.browser.setHtml(full_html)
        
        btn_close = QPushButton("Close Preview")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def handle_links(self, url):
        if url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)
        else:
            self.browser.setSource(url)

class MarkdownToolbar(QWidget):
    def __init__(self, text_edit, parent=None):
        super().__init__(parent)
        self.text_edit = text_edit
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.add_btn("B", self.toggle_bold, "Bold (**text**)")
        self.add_btn("I", self.toggle_italic, "Italic (*text*)")
        self.add_btn("Code", self.insert_code_block, "Insert Code Block")
        self.add_btn("Table", self.insert_table, "Insert Table Template")
        layout.addStretch()

    def add_btn(self, label, func, tooltip):
        btn = QToolButton()
        btn.setText(label)
        btn.setToolTip(tooltip)
        btn.setFixedSize(40, 24)
        btn.setStyleSheet("QToolButton { font-weight: bold; border: 1px solid #555; border-radius: 3px; background: #333; color: #eee; } QToolButton:hover { background: #555; }")
        btn.clicked.connect(func)
        self.layout().addWidget(btn)

    def wrap_selection(self, prefix, suffix):
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            cursor.insertText(f"{prefix}{suffix}")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(suffix))
        else:
            text = cursor.selectedText()
            cursor.insertText(f"{prefix}{text}{suffix}")
        self.text_edit.setFocus()

    def toggle_bold(self):
        self.wrap_selection("**", "**")

    def toggle_italic(self):
        self.wrap_selection("*", "*")

    def insert_code_block(self):
        cursor = self.text_edit.textCursor()
        cursor.insertText("\n```\nCODE_HERE\n```\n")
        self.text_edit.setFocus()

    def insert_table(self):
        cursor = self.text_edit.textCursor()
        table_template = (
            "\n| Header 1 | Header 2 | Header 3 |\n"
            "|---|---|---|\n"
            "| Row 1    | Data     | Data     |\n"
            "| Row 2    | Data     | Data     |\n"
        )
        cursor.insertText(table_template)
        self.text_edit.setFocus()

class ReportTabWidget(QWidget):
    def __init__(self, db_path=None, project_name="Target", parent=None):
        super().__init__(parent)
        self.project_folder = None
        self.db_path = None
        self.project_name = project_name
        
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # --- Left Pane ---
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        # Category
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Vulnerability Category:"))
        manage_templates_btn = QPushButton("Manage Templates")
        manage_templates_btn.setMaximumWidth(150)
        category_layout.addWidget(manage_templates_btn)
        input_layout.addLayout(category_layout)
        
        self.category_combo = QComboBox()
        input_layout.addWidget(self.category_combo)

        # Title
        input_layout.addWidget(QLabel("Report Title (Filename):"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("e.g. XSS (Login Page)")
        input_layout.addWidget(self.title_input)
        
        # URL
        input_layout.addWidget(QLabel("Vulnerable URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/page?param=value")
        input_layout.addWidget(self.url_input)
        
        # Impact
        input_layout.addWidget(QLabel("Custom Impact / Notes:"))
        self.impact_input = QTextEdit()
        self.impact_input.setPlaceholderText("Add custom details here... (Overrides template impact)")
        self.impact_input.setMaximumHeight(100)
        input_layout.addWidget(self.impact_input)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_project_btn = QPushButton("Save Report")
        self.save_project_btn.setStyleSheet("background-color: #2d5a2d; font-weight: bold;") 
        self.preview_btn = QPushButton("Preview Report")
        self.preview_btn.setStyleSheet("background-color: #3a7bd5; font-weight: bold;")
        btn_layout.addWidget(self.save_project_btn)
        btn_layout.addWidget(self.preview_btn)
        input_layout.addLayout(btn_layout)
        
        # PDF Export
        self.pdf_btn = QPushButton("Export All to PDF")
        self.pdf_btn.setStyleSheet("background-color: #e65100; font-weight: bold; margin-top: 5px;")
        self.pdf_btn.clicked.connect(self.export_all_to_pdf)
        input_layout.addWidget(self.pdf_btn)
        
        # List
        input_layout.addSpacing(15)
        input_layout.addWidget(QLabel("<b>Saved Project Reports:</b>"))
        
        self.reports_list = QListWidget()
        # Force styling to match the theme (Dark BG, Cyan Text)
        self.reports_list.setStyleSheet("""
            QListWidget {
                background-color: #2f2f40;
                color: #00d2ff;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #3a7bd5;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3e3e50;
            }
        """)
        input_layout.addWidget(self.reports_list)
        
        # --- Right Pane ---
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("background-color: #333; color: #aaa; padding: 5px; border-radius: 4px; margin-bottom: 5px;")
        preview_layout.addWidget(self.status_label)

        preview_label = QLabel("<i>Editable Report Preview (Markdown)</i>")
        preview_label.setStyleSheet("color: gray;")
        preview_layout.addWidget(preview_label)

        self.desc_preview = self.create_preview_section(preview_layout, "Description")
        self.impact_preview = self.create_preview_section(preview_layout, "Impact")
        self.validation_preview = self.create_preview_section(preview_layout, "Validation Steps", add_screenshot_btn=True)
        self.fix_preview = self.create_preview_section(preview_layout, "Recommended Fix")
        
        splitter.addWidget(input_widget)
        splitter.addWidget(preview_widget)
        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter)
        
        # Connections
        manage_templates_btn.clicked.connect(self.open_template_editor)
        self.category_combo.currentIndexChanged.connect(self.on_category_selected)
        self.url_input.textChanged.connect(self.update_dynamic_fields)
        self.impact_input.textChanged.connect(self.update_dynamic_fields)
        self.save_project_btn.clicked.connect(self.save_project_template)
        self.preview_btn.clicked.connect(self.show_single_preview)
        self.reports_list.itemClicked.connect(self.load_report_from_list)
        
        if db_path:
            self.set_project_db_path(db_path)
        else:
            self.load_categories()

        self.on_category_selected()

    def set_project_db_path(self, db_path):
        if not db_path: return
        self.db_path = db_path
        self.project_folder = os.path.dirname(db_path)
        self.load_categories()
        self.refresh_reports_list()

    def refresh_reports_list(self):
        self.reports_list.clear()
        if not self.project_folder: return
        reports_dir = os.path.join(self.project_folder, "reports")
        if not os.path.exists(reports_dir): return
        files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
        files.sort()
        for f in files:
            item = QListWidgetItem(os.path.splitext(f)[0])
            self.reports_list.addItem(item)

    def load_report_from_list(self, item):
        if not self.project_folder: return
        filename = item.text() + ".md"
        filepath = os.path.join(self.project_folder, "reports", filename)
        if not os.path.exists(filepath): return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            data = command_db.parse_markdown_template(item.text(), content)
            self.current_template_data = data
            self.title_input.setText(item.text()) 
            self.populate_fields(data)
            self.update_status(item.text(), "SAVED")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load report: {e}")

    def create_preview_section(self, parent_layout, title, add_screenshot_btn=False):
        section_layout = QVBoxLayout()
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel(f"<b>{title}</b>"))
        top_bar.addStretch()
        if add_screenshot_btn:
            shot_btn = QPushButton("Insert Screenshot")
            shot_btn.setCursor(Qt.PointingHandCursor)
            shot_btn.setToolTip("Insert screenshot from file.")
            top_bar.addWidget(shot_btn)
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.PointingHandCursor)
        top_bar.addWidget(copy_btn)
        section_layout.addLayout(top_bar)

        text_edit = QTextEdit() 
        text_edit.setMinimumHeight(100)
        text_edit.setStyleSheet("font-family: Consolas, Monaco, monospace; border: 1px solid #444;")
        toolbar = MarkdownToolbar(text_edit)
        section_layout.addWidget(toolbar)
        section_layout.addWidget(text_edit)
        
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(text_edit))
        if add_screenshot_btn:
             shot_btn.clicked.connect(lambda: self.insert_screenshot(text_edit))
        parent_layout.addLayout(section_layout)
        return text_edit

    def load_categories(self):
        current = self.category_combo.currentText()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        categories = set(command_db.get_all_template_categories())
        self.category_combo.addItems(sorted(list(categories)))
        index = self.category_combo.findText(current)
        if index != -1: self.category_combo.setCurrentIndex(index)
        self.category_combo.blockSignals(False)
        self.refresh_reports_list()

    def on_category_selected(self):
        category = self.category_combo.currentText()
        if not category:
            self.clear_fields()
            self.status_label.setText("Ready")
            self.status_label.setStyleSheet("background-color: #333; color: #aaa;")
            return
        data = command_db.get_template_by_category(category)
        if not data: return
        self.current_template_data = data
        self.title_input.setText(category)
        self.populate_fields(data)
        self.update_status(category, "GLOBAL")
        self.update_dynamic_fields()

    def populate_fields(self, data):
        self.desc_preview.setPlainText(data.get('description', ''))
        self.impact_preview.setPlainText(data.get('impact', ''))
        self.validation_preview.setPlainText(data.get('validation_steps', ''))
        self.fix_preview.setPlainText(data.get('fix_recommendation', ''))

    def update_status(self, name, source):
        if source == "SAVED":
            self.status_label.setText(f"[SAVED REPORT] {name}")
            self.status_label.setStyleSheet("background-color: #1b2e1b; color: #4caf50; border: 1px solid #4caf50; padding: 8px; border-radius: 4px; font-weight: bold;")
        else:
            self.status_label.setText(f"[NEW DRAFT] {name}")
            self.status_label.setStyleSheet("background-color: #3e2704; color: #ff9800; border: 1px solid #ff9800; padding: 8px; border-radius: 4px; font-weight: bold;")

    def update_dynamic_fields(self):
        if not hasattr(self, 'current_template_data') or not self.current_template_data: return
        url = self.url_input.text() or "{URL}"
        custom_impact = self.impact_input.toPlainText()
        raw_desc = self.current_template_data.get('description', '')
        self.desc_preview.setPlainText(raw_desc.replace("{URL}", url))
        if custom_impact: self.impact_preview.setPlainText(custom_impact)
        else: self.impact_preview.setPlainText(self.current_template_data.get('impact', ''))

    def save_project_template(self):
        if not self.project_folder:
            QMessageBox.warning(self, "Error", "No project loaded.")
            return
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a Report Title.")
            return
        safe_filename = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
        reports_dir = os.path.join(self.project_folder, "reports")
        if not os.path.exists(reports_dir): os.makedirs(reports_dir)
            
        content = command_db.create_markdown_content(
            self.desc_preview.toPlainText(),
            self.impact_preview.toPlainText(),
            self.validation_preview.toPlainText(),
            self.fix_preview.toPlainText()
        )
        file_path = os.path.join(reports_dir, f"{safe_filename}.md")
        try:
            with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
            QMessageBox.information(self, "Saved", f"Report saved as:\n{safe_filename}.md")
            self.refresh_reports_list()
            self.update_status(safe_filename, "SAVED")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save template: {e}")

    def insert_screenshot(self, text_widget):
        if not self.project_folder:
            QMessageBox.warning(self, "Error", "Open a project first.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Screenshot", "", "Images (*.png *.jpg *.jpeg *.gif)")
        if not file_path: return
        images_dir = os.path.join(self.project_folder, "reports", "images")
        if not os.path.exists(images_dir): os.makedirs(images_dir)
        filename = os.path.basename(file_path)
        dest_path = os.path.join(images_dir, filename)
        try: shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy image: {e}")
            return
        markdown_tag = f"\n![Screenshot](images/{filename})\n"
        text_widget.insertPlainText(markdown_tag)
        text_widget.setFocus()

    def show_single_preview(self):
        title = self.title_input.text() or "Preview"
        full_md = f"# {title}\n\n## Description\n{self.desc_preview.toPlainText()}\n\n## Impact\n{self.impact_preview.toPlainText()}\n\n## Validation Steps\n{self.validation_preview.toPlainText()}\n\n## Fix Recommendation\n{self.fix_preview.toPlainText()}\n"
        dialog = ReportPreviewDialog(full_md, self.project_folder, self)
        dialog.exec_()

    def export_all_to_pdf(self):
        if not self.project_folder:
            QMessageBox.warning(self, "Error", "No active project.")
            return

        reports_dir = os.path.join(self.project_folder, "reports")
        if not os.path.exists(reports_dir):
            QMessageBox.warning(self, "No Reports", "No reports found in project folder.")
            return

        files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
        if not files:
            QMessageBox.warning(self, "No Reports", "No saved reports to export.")
            return
        files.sort()

        # Automatic Target Name
        project_name = self.project_name if self.project_name else "Penetration Test"
        today_date = datetime.datetime.now().strftime("%B %d, %Y")

        # HTML PARTS ACCUMULATOR
        html_pages = []

        # --- 1. TITLE PAGE (Pure HTML, no markdown wrapper) ---
        title_page = f"""
        <div class="title-container">
            <div class="title-main">Vulnerability Assessment Report</div>
            <div class="title-sub">Target: {project_name}</div>
            <div class="title-meta">Generated: {today_date}<br>Tool: CyberSec Buddy</div>
        </div>
        """
        html_pages.append(title_page)

        # --- 2. INDEX / TOC (Markdown rendered to HTML) ---
        toc_md = "# Index of Findings\n\nThe following vulnerabilities were identified:\n\n"
        for i, filename in enumerate(files, 1):
             title = os.path.splitext(filename)[0]
             # Use a span/div class for TOC items to control spacing
             toc_md += f"<div class='toc-item'><b>{i}.</b> {title}</div>\n"
        
        html_pages.append(render_markdown_body(toc_md, self.project_folder, pdf_mode=True))

        # --- 3. VULNERABILITY DETAILS ---
        for filename in files:
            filepath = os.path.join(reports_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Prepend the Title of the Vulnerability
                full_report_md = f"# {os.path.splitext(filename)[0]}\n\n{content}"
                
                # Render individual report body
                report_html = render_markdown_body(full_report_md, self.project_folder, pdf_mode=True)
                html_pages.append(report_html)
                
            except Exception as e:
                print(f"Skipping {filename}: {e}")

        # --- 4. JOIN WITH PAGE BREAKS ---
        # We use a horizontal rule styled as a page break
        page_break_html = '<hr class="page-break">'
        
        full_body = page_break_html.join(html_pages)
        
        # Wrap in HTML/HEAD/STYLE
        style = get_report_style(pdf_mode=True)
        final_html = f"<html><head>{style}</head><body>{full_body}</body></html>"

        # --- 5. PRINT ---
        pdf_path, _ = QFileDialog.getSaveFileName(self, "Export PDF", os.path.join(self.project_folder, f"Report_{project_name}.pdf"), "PDF Files (*.pdf)")
        if not pdf_path: return
        if not pdf_path.endswith('.pdf'): pdf_path += ".pdf"

        document = QTextDocument()
        document.setHtml(final_html)
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(pdf_path)
        printer.setPageSize(QPrinter.A4)
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
        
        document.print_(printer)
        QMessageBox.information(self, "Success", f"Report exported successfully!\nLocation: {pdf_path}")

    def clear_fields(self):
        self.desc_preview.clear()
        self.impact_preview.clear()
        self.validation_preview.clear()
        self.fix_preview.clear()
        self.current_template_data = None

    def open_template_editor(self):
        dialog = TemplateEditorDialog(self)
        dialog.exec_()
        self.load_categories()

    def copy_to_clipboard(self, text_widget):
        clipboard = QApplication.clipboard()
        clipboard.setText(text_widget.toPlainText())
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Copied to clipboard!")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        msg.show()
        QTimer.singleShot(1000, msg.accept)