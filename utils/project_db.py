import sqlite3
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, 
                             QMessageBox, QLineEdit, QDateEdit, QHBoxLayout, QFormLayout)
from PyQt5.QtCore import Qt, QDate

def initialize_project_db(folder_path, db_filename="project_data.db"):
    """Creates the SQLite DB and tables in the specified folder."""
    db_path = os.path.join(folder_path, db_filename)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Table: Project Metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            engagement_type TEXT,
            deadline TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table: Scope / Domains
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            in_scope BOOLEAN DEFAULT 1
        )
    ''')

    # Table: Scan Results (Placeholder for future)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT,
            result_output TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    return db_path

def save_project_details(db_path, client, eng_type, deadline, domain_list):
    """Inserts the initial wizard data into the DB."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Save Metadata
    c.execute("INSERT INTO project_info (client_name, engagement_type, deadline) VALUES (?, ?, ?)",
              (client, eng_type, deadline))
    
    # Save Domains
    for d in domain_list:
        clean_d = d.strip()
        if clean_d:
            c.execute("INSERT INTO domains (domain) VALUES (?)", (clean_d,))
            
    conn.commit()
    conn.close()

def update_project_metadata(db_path, client_name, deadline):
    """Updates the client name and deadline in the database."""
    if not os.path.exists(db_path): return False
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            UPDATE project_info 
            SET client_name = ?, deadline = ? 
            WHERE id = (SELECT MAX(id) FROM project_info)
        """, (client_name, deadline))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating metadata: {e}")
        return False

def update_project_domains(db_path, domains_text):
    """Updates the domains table to match the new list."""
    if not os.path.exists(db_path): return False
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 1. Clear existing domains
        c.execute("DELETE FROM domains")
        
        # 2. Insert new domains
        domain_list = [d.strip() for d in domains_text.splitlines() if d.strip()]
        for d in domain_list:
            c.execute("INSERT INTO domains (domain) VALUES (?)", (d,))
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating domains: {e}")
        return False

def load_project_data(db_path):
    """Reads project info to populate the UI."""
    data = {}
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get Metadata
    c.execute("SELECT * FROM project_info ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        data['client_name'] = row['client_name']
        data['engagement_type'] = row['engagement_type']
        data['deadline'] = row['deadline']
    
    # Get Domains
    c.execute("SELECT domain FROM domains")
    domains = [r['domain'] for r in c.fetchall()]
    data['domains'] = domains

    conn.close()
    return data

def is_valid_project_db(db_path):
    """Checks if a file is a valid project DB."""
    if not os.path.exists(db_path): return False
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_info'")
        result = c.fetchone()
        conn.close()
        return result is not None
    except:
        return False

# ---------------------------------------------------------
# EDITOR DIALOG
# ---------------------------------------------------------
class ProjectEditDialog(QDialog):
    """
    Dialog to view and EDIT project information.
    Modifies DB for metadata and Text Files for content.
    """
    def __init__(self, parent, db_path):
        super().__init__(parent)
        self.db_path = db_path
        self.project_dir = os.path.dirname(db_path)
        self.setWindowTitle("Edit Project Settings")
        self.resize(700, 800)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QLabel { font-size: 14px; color: #e0e0e0; font-weight: bold; }
            QLineEdit, QDateEdit, QTextEdit { 
                background-color: #2f2f40; color: #00d2ff; 
                border: 1px solid #4a4a5e; border-radius: 4px; padding: 6px;
                font-family: monospace; font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #00d2ff; }
            QPushButton { 
                background-color: #3e3e50; color: white; 
                padding: 10px; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #4e4e60; border: 1px solid #00d2ff; }
            QPushButton#SaveBtn { background-color: #28a745; color: white; border: none; }
            QPushButton#SaveBtn:hover { background-color: #218838; }
        """)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 1. METADATA SECTION
        meta_layout = QFormLayout()
        meta_layout.setSpacing(10)
        
        self.inp_client = QLineEdit()
        self.inp_deadline = QDateEdit()
        self.inp_deadline.setCalendarPopup(True)
        self.inp_deadline.setDisplayFormat("yyyy-MM-dd")
        
        meta_layout.addRow("Client Name:", self.inp_client)
        meta_layout.addRow("Deadline:", self.inp_deadline)
        
        layout.addLayout(meta_layout)
        
        # 2. FILES SECTION
        # Domains
        layout.addWidget(QLabel("Target Domains (domains.txt):"))
        self.txt_domains = QTextEdit()
        layout.addWidget(self.txt_domains)
        
        # Scope
        layout.addWidget(QLabel("Scope / IP Ranges (scope.txt):"))
        self.txt_scope = QTextEdit()
        layout.addWidget(self.txt_scope)
        
        # 3. BUTTONS
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("SaveBtn")
        btn_save.clicked.connect(self.save_changes)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)

    def load_data(self):
        # Load DB Metadata
        data = load_project_data(self.db_path)
        if data:
            self.inp_client.setText(data.get('client_name', ''))
            deadline_str = data.get('deadline', '')
            if deadline_str:
                self.inp_deadline.setDate(QDate.fromString(deadline_str, "yyyy-MM-dd"))
            else:
                self.inp_deadline.setDate(QDate.currentDate())

        # Load Text Files
        dom_file = os.path.join(self.project_dir, "domains.txt")
        if os.path.exists(dom_file):
            with open(dom_file, 'r', encoding='utf-8') as f:
                self.txt_domains.setPlainText(f.read())
        
        scope_file = os.path.join(self.project_dir, "scope.txt")
        if os.path.exists(scope_file):
            with open(scope_file, 'r', encoding='utf-8') as f:
                self.txt_scope.setPlainText(f.read())

    def save_changes(self):
        # 1. Update DB Metadata
        new_client = self.inp_client.text().strip()
        new_deadline = self.inp_deadline.date().toString("yyyy-MM-dd")
        
        if not new_client:
            QMessageBox.warning(self, "Error", "Client Name cannot be empty.")
            return

        success_meta = update_project_metadata(self.db_path, new_client, new_deadline)
        
        # 2. Update DB Domains (Sync DB with Text)
        success_domains = update_project_domains(self.db_path, self.txt_domains.toPlainText())

        if not success_meta:
            QMessageBox.critical(self, "Error", "Failed to update database metadata.")
            return

        # 3. Update Files
        try:
            dom_file = os.path.join(self.project_dir, "domains.txt")
            with open(dom_file, 'w', encoding='utf-8') as f:
                f.write(self.txt_domains.toPlainText())
            
            scope_file = os.path.join(self.project_dir, "scope.txt")
            with open(scope_file, 'w', encoding='utf-8') as f:
                f.write(self.txt_scope.toPlainText())
                
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Failed to write files: {str(e)}")
            return

        QMessageBox.information(self, "Success", "Project information updated successfully.")
        self.accept()