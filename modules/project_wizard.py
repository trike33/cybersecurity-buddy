import os
import shutil
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QDateEdit, QMessageBox, QFileDialog, QPushButton, QDialog, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import QDate, Qt

# Import your existing DB logic
from utils import project_db

class SimpleTextEditorDialog(QDialog):
    """A simple popup to let the user type in domains or scope IPs manually."""
    def __init__(self, title, current_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout()
        
        lbl = QLabel("Enter content (one per line):")
        layout.addWidget(lbl)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(current_text)
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)

    def get_text(self):
        return self.text_edit.toPlainText()

class ProjectSetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project Setup")
        self.setFixedSize(700, 500)
        
        # Style
        self.setStyleSheet("""
            QWizard { background-color: #1e1e2f; color: white; }
            QLabel { color: #e0e0e0; font-size: 14px; }
            QLineEdit, QComboBox, QDateEdit, QTextEdit { 
                background-color: #2f2f40; color: white; border: 1px solid #4a4a5e; padding: 5px; border-radius: 4px;
            }
            QPushButton {
                background-color: #4a4a5e; color: white; border: none; padding: 5px 10px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #5b5b75; }
        """)

        # Add Pages
        self.details_page = ProjectDetailsPage()
        self.scope_page = ScopeSelectionPage()
        
        self.addPage(self.details_page)
        self.addPage(self.scope_page)
        
        self.project_db_path = None

    def accept(self):
        # --- 1. Gather Data ---
        client = self.field("client_name")
        eng_type = self.field("engagement_type")
        deadline = self.field("deadline").toString("yyyy-MM-dd")
        root_path = self.field("root_path")

        # Get Scope/Domain data directly from the page instance
        domain_mode = self.scope_page.domain_mode  # 'file' or 'content'
        domain_data = self.scope_page.domain_data  # Path or Raw Text
        
        scope_mode = self.scope_page.scope_mode
        scope_data = self.scope_page.scope_data

        # --- 2. Create Directory ---
        folder_name = f"{client.replace(' ', '_')}_Engagement"
        full_project_path = os.path.join(root_path, folder_name)
        
        if not os.path.exists(full_project_path):
            try:
                os.makedirs(full_project_path)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {e}")
                return

        # --- 3. Handle Domains File ---
        final_domains_path = os.path.join(full_project_path, "domains.txt")
        
        try:
            if domain_mode == 'content':
                # Write the manual content to a new file
                with open(final_domains_path, 'w', encoding='utf-8') as f:
                    f.write(domain_data)
            elif domain_mode == 'file' and os.path.exists(domain_data):
                # Copy the selected file to the project folder
                shutil.copy(domain_data, final_domains_path)
            else:
                # Create empty file if nothing provided
                with open(final_domains_path, 'w') as f: f.write("")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to save domains file: {e}")

        # --- 4. Handle Scope File ---
        final_scope_path = os.path.join(full_project_path, "scope.txt")
        
        try:
            if scope_mode == 'content':
                with open(final_scope_path, 'w', encoding='utf-8') as f:
                    f.write(scope_data)
            elif scope_mode == 'file' and os.path.exists(scope_data):
                shutil.copy(scope_data, final_scope_path)
            else:
                with open(final_scope_path, 'w') as f: f.write("")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to save scope file: {e}")

        # --- 5. Initialize DB ---
        self.project_db_path = project_db.initialize_project_db(full_project_path)
        
        # --- 6. Save Data to DB ---
        # We read the list back from the file we just created/copied to ensure DB matches file reality
        try:
            with open(final_domains_path, 'r') as f:
                domain_list = [line.strip() for line in f.readlines() if line.strip()]
        except:
            domain_list = []

        project_db.save_project_details(self.project_db_path, client, eng_type, deadline, domain_list)
        
        super().accept()

class ProjectDetailsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Project Details")
        self.setSubTitle("Please enter the core information for this engagement.")
        
        layout = QVBoxLayout()
        
        # Client Name
        layout.addWidget(QLabel("Client / Project Name:"))
        self.inp_client = QLineEdit()
        self.registerField("client_name*", self.inp_client)
        layout.addWidget(self.inp_client)

        # Engagement Type
        layout.addWidget(QLabel("Engagement Type:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Pentest", "Bug Bounty"])
        self.registerField("engagement_type", self.combo_type, "currentText")
        layout.addWidget(self.combo_type)

        # Deadline
        layout.addWidget(QLabel("Deadline:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate().addDays(14))
        self.date_edit.setCalendarPopup(True)
        self.registerField("deadline", self.date_edit)
        layout.addWidget(self.date_edit)

        # Root Directory
        layout.addWidget(QLabel("Save Project In:"))
        self.inp_path = QLineEdit(os.path.expanduser("~"))
        self.registerField("root_path", self.inp_path)
        layout.addWidget(self.inp_path)

        self.setLayout(layout)

class ScopeSelectionPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Scope & Targets")
        self.setSubTitle("Select existing files or create new lists for domains and scope.")

        self.layout = QVBoxLayout()

        # --- Variables to store state ---
        self.domain_mode = None # 'file' or 'content'
        self.domain_data = ""
        self.scope_mode = None
        self.scope_data = ""

        # --- Domains Section ---
        self.layout.addWidget(QLabel("<b>Target Domains List:</b>"))
        
        h_layout_dom = QHBoxLayout()
        self.inp_domains = QLineEdit()
        self.inp_domains.setPlaceholderText("Select a file or Create New...")
        self.inp_domains.setReadOnly(True) # User must use buttons
        self.registerField("domains_file_field", self.inp_domains) # Just for validation if needed
        
        btn_dom_browse = QPushButton("Browse File")
        btn_dom_browse.clicked.connect(self.browse_domains)
        
        btn_dom_create = QPushButton("Create/Edit")
        btn_dom_create.clicked.connect(self.create_domains)

        h_layout_dom.addWidget(self.inp_domains)
        h_layout_dom.addWidget(btn_dom_browse)
        h_layout_dom.addWidget(btn_dom_create)
        self.layout.addLayout(h_layout_dom)

        # --- Scope Section ---
        self.layout.addSpacing(20)
        self.layout.addWidget(QLabel("<b>Scope / IP Ranges List:</b>"))
        
        h_layout_scope = QHBoxLayout()
        self.inp_scope = QLineEdit()
        self.inp_scope.setPlaceholderText("Select a file or Create New...")
        self.inp_scope.setReadOnly(True)
        self.registerField("scope_file_field", self.inp_scope)
        
        btn_scope_browse = QPushButton("Browse File")
        btn_scope_browse.clicked.connect(self.browse_scope)
        
        btn_scope_create = QPushButton("Create/Edit")
        btn_scope_create.clicked.connect(self.create_scope)

        h_layout_scope.addWidget(self.inp_scope)
        h_layout_scope.addWidget(btn_scope_browse)
        h_layout_scope.addWidget(btn_scope_create)
        self.layout.addLayout(h_layout_scope)

        self.setLayout(self.layout)

