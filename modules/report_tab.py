import os
import shutil
import markdown
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox,
    QLineEdit, QTextEdit, QPushButton, QApplication, QMessageBox, QFileDialog,
    QDialog, QTextBrowser, QListWidget, QListWidgetItem, QToolButton
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QTextCursor, QTextDocument
from PyQt5.QtPrintSupport import QPrinter
from utils import db as command_db
from modules.dialogs import TemplateEditorDialog

# --- Helper: Render Logic (Shared between Preview and PDF) ---
def render_markdown_to_html(markdown_text, project_folder):
    """
    Converts markdown to HTML with CSS and fixed image paths.
    """
    html_body = markdown.markdown(markdown_text, extensions=['fenced_code', 'tables'])
    
    if project_folder:
        reports_img_dir = os.path.join(project_folder, "reports", "images")
        base_url = QUrl.fromLocalFile(reports_img_dir).toString()
        html_body = html_body.replace('src="images/', f'src="{base_url}/')

    style = """
    <style>
        body { font-family: sans-serif; color: #333; }
        h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 5px; margin-top: 30px; }
        h2 { color: #e67e22; margin-top: 20px; }
        h3 { color: #34495e; }
        code { background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace; color: #c7254e; }
        pre { background-color: #2b2b2b; color: #f8f8f2; padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0; }
        pre code { background-color: transparent; color: #f8f8f2; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        img { max-width: 100%; height: auto; border: 1px solid #ddd; padding: 5px; margin: 10px 0; display: block; }
        blockquote { border-left: 4px solid #ddd; padding-left: 10px; color: #666; font-style: italic; }
        .page-break { page-break-after: always; }
    </style>
    """
    
    return f"<html><head>{style}</head><body>{html_body}</body></html>"

class ReportPreviewDialog(QDialog):
    """
    A dialog that renders the compiled Markdown report into HTML.
    """
    def __init__(self, markdown_content, project_folder=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Report Preview")
        self.resize(1200, 900)
        
        layout = QVBoxLayout(self)
        
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self.handle_links)
        
        # Dark theme for the browser window background
        self.browser.setStyleSheet("background-color: #1e1e2f; border: none;")
        
        layout.addWidget(self.browser)
        
        base_html = render_markdown_to_html(markdown_content, project_folder)
        dark_override = """
        <style>
            body { background-color: #1e1e2f; color: #e0e0e0; }
            h1 { color: #00d2ff; border-bottom: 2px solid #00d2ff; }
            h2 { color: #ffca28; }
            table, th, td { border-color: #444; color: #e0e0e0; }
            th { background-color: #2f2f40; }
            code { background-color: #2f2f40; color: #ff79c6; }
        </style>
        """
        self.browser.setHtml(base_html.replace("</head>", f"{dark_override}</head>"))
        
        btn_close = QPushButton("Close Preview")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def handle_links(self, url):
        if url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)
        else:
            self.browser.setSource(url)

class MarkdownToolbar(QWidget):
    """A small toolbar widget attached to a QTextEdit for formatting."""
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
    """
    A tab for generating and managing vulnerability reports.
    """
    
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.project_folder = None
        self.db_path = None
        
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # --- Left Pane (Inputs & List) ---
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        # 1. Category Selection
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Vulnerability Category:"))
        manage_templates_btn = QPushButton("Manage Templates")
        manage_templates_btn.setMaximumWidth(150)
        category_layout.addWidget(manage_templates_btn)
        input_layout.addLayout(category_layout)
        
        self.category_combo = QComboBox()
        input_layout.addWidget(self.category_combo)

        # 2. Report Title (NEW)
        input_layout.addWidget(QLabel("Report Title (Filename):"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("e.g. XSS (Login Page)")
        input_layout.addWidget(self.title_input)
        
        # 3. Vulnerable URL
        input_layout.addWidget(QLabel("Vulnerable URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/page?param=value")
        input_layout.addWidget(self.url_input)
        
        # 4. Custom Impact
        input_layout.addWidget(QLabel("Custom Impact / Notes:"))
        self.impact_input = QTextEdit()
        self.impact_input.setPlaceholderText("Add custom details here... (Overrides template impact)")
        self.impact_input.setMaximumHeight(100)
        input_layout.addWidget(self.impact_input)

        # 5. Action Buttons
        btn_layout = QHBoxLayout()
        self.save_project_btn = QPushButton("Save Report")
        self.save_project_btn.setToolTip("Saves this report as a file using the Title provided.")
        self.save_project_btn.setStyleSheet("background-color: #2d5a2d; font-weight: bold;") 
        
        self.preview_btn = QPushButton("Preview Report")
        self.preview_btn.setToolTip("Render this single report.")
        self.preview_btn.setStyleSheet("background-color: #3a7bd5; font-weight: bold;")
        
        btn_layout.addWidget(self.save_project_btn)
        btn_layout.addWidget(self.preview_btn)
        input_layout.addLayout(btn_layout)
        
        # 6. PDF Export
        self.pdf_btn = QPushButton("Export All to PDF")
        self.pdf_btn.setStyleSheet("background-color: #e65100; font-weight: bold; margin-top: 5px;")
        self.pdf_btn.clicked.connect(self.export_all_to_pdf)
        input_layout.addWidget(self.pdf_btn)
        
        # 7. Saved Reports List
        input_layout.addSpacing(15)
        input_layout.addWidget(QLabel("<b>Saved Project Reports:</b>"))
        
        self.reports_list = QListWidget()
        self.reports_list.setAlternatingRowColors(True)
        self.reports_list.setToolTip("Click to load and edit a saved report.")
        input_layout.addWidget(self.reports_list)
        
        # --- Right Pane (Editable Preview) ---
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        # --- STATUS INDICATOR (MOVED TO TOP RIGHT) ---
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        # Default styling
        self.status_label.setStyleSheet("background-color: #333; color: #aaa; padding: 5px; border-radius: 4px; margin-bottom: 5px;")
        preview_layout.addWidget(self.status_label)
        # ---------------------------------------------

        preview_label = QLabel("<i>Editable Report Preview (Markdown)</i>")
        preview_label.setStyleSheet("color: gray;")
        preview_layout.addWidget(preview_label)

        self.desc_preview = self.create_preview_section(preview_layout, "Description")
        self.impact_preview = self.create_preview_section(preview_layout, "Impact")
        self.validation_preview = self.create_preview_section(
            preview_layout, "Validation Steps", add_screenshot_btn=True
        )
        self.fix_preview = self.create_preview_section(preview_layout, "Recommended Fix")
        
        splitter.addWidget(input_widget)
        splitter.addWidget(preview_widget)
        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter)
        
        # --- Connections ---
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
            # Use filename without extension as the item text
            report_title = os.path.splitext(f)[0]
            item = QListWidgetItem(report_title)
            self.reports_list.addItem(item)

    def load_report_from_list(self, item):
        """Loads a specific file from the list."""
        if not self.project_folder: return
        
        filename = item.text() + ".md"
        filepath = os.path.join(self.project_folder, "reports", filename)
        
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "Error", "File not found.")
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse content (using the filename as category for parsing structure)
            data = command_db.parse_markdown_template(item.text(), content)
            
            self.current_template_data = data
            self.title_input.setText(item.text()) # Set Title to Filename
            
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
        current_selection = self.category_combo.currentText()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        
        categories = set()
        global_cats = command_db.get_all_template_categories()
        categories.update(global_cats)
        
        # We don't necessarily need to load local files into the COMBO anymore
        # because the LIST handles distinct files. But we keep global categories
        # to allow creating new reports from templates.
        
        sorted_cats = sorted(list(categories))
        self.category_combo.addItems(sorted_cats)
        
        index = self.category_combo.findText(current_selection)
        if index != -1:
            self.category_combo.setCurrentIndex(index)
        
        self.category_combo.blockSignals(False)
        self.refresh_reports_list()

    def on_category_selected(self):
        """Called when user picks a category from the dropdown (Start New Draft)."""
        category = self.category_combo.currentText()
        if not category:
            self.clear_fields()
            self.status_label.setText("Ready")
            self.status_label.setStyleSheet("background-color: #333; color: #aaa;")
            return

        # Load GLOBAL Template
        data = command_db.get_template_by_category(category)
        if not data: return

        self.current_template_data = data
        
        # Set Title to Category Name (as a default starting point)
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
        if not hasattr(self, 'current_template_data') or not self.current_template_data:
            return

        url = self.url_input.text() or "{URL}"
        custom_impact = self.impact_input.toPlainText()
        raw_desc = self.current_template_data.get('description', '')
        self.desc_preview.setPlainText(raw_desc.replace("{URL}", url))

        if custom_impact:
             self.impact_preview.setPlainText(custom_impact)
        else:
             self.impact_preview.setPlainText(self.current_template_data.get('impact', ''))

    def save_project_template(self):
        if not self.project_folder:
            QMessageBox.warning(self, "Error", "No project loaded.")
            return

        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a Report Title.")
            return

        # Sanitize filename
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
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
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
        try:
            shutil.copy2(file_path, dest_path)
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

        combined_md = f"# Vulnerability Assessment Report\nGenerated by CyberSec Buddy\n\n"
        for filename in files:
            filepath = os.path.join(reports_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                combined_md += f"\n\n<div class='page-break'></div>\n\n# {os.path.splitext(filename)[0]}\n\n"
                combined_md += content
            except Exception as e:
                print(f"Skipping {filename}: {e}")

        html_content = render_markdown_to_html(combined_md, self.project_folder)

        pdf_path, _ = QFileDialog.getSaveFileName(self, "Export PDF", os.path.join(self.project_folder, "Final_Report.pdf"), "PDF Files (*.pdf)")
        if not pdf_path: return
        if not pdf_path.endswith('.pdf'): pdf_path += ".pdf"

        document = QTextDocument()
        document.setHtml(html_content)
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(pdf_path)
        printer.setPageSize(QPrinter.A4)
        
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