import sqlite3
import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QMessageBox
from PyQt5.QtCore import Qt

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
    
def show_project_info_dialog(parent, db_path):
    """
    Displays a modal dialog with project details, domains, and scope.
    Reads metadata from DB and full lists from text files.
    """
    if not db_path or not os.path.exists(db_path):
        QMessageBox.warning(parent, "Error", "No valid project database found.")
        return

    # 1. Load Metadata from DB
    data = load_project_data(db_path) # Calls the function existing in this file
    if not data:
        QMessageBox.warning(parent, "Error", "Could not load project data.")
        return

    project_dir = os.path.dirname(db_path)
    client = data.get('client_name', 'Unknown')
    eng_type = data.get('engagement_type', 'Unknown')
    deadline = data.get('deadline', 'Unknown')

    # 2. Read Text Files (Domains & Scope)
    # We prefer the text files over the DB for the "View" because they might be manually edited
    domains_text = "No domains.txt found."
    scope_text = "No scope.txt found."

    dom_file = os.path.join(project_dir, "domains.txt")
    if os.path.exists(dom_file):
        with open(dom_file, 'r', encoding='utf-8') as f:
            domains_text = f.read()

    scope_file = os.path.join(project_dir, "scope.txt")
    if os.path.exists(scope_file):
        with open(scope_file, 'r', encoding='utf-8') as f:
            scope_text = f.read()

    # 3. Build UI
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Project Info: {client}")
    dlg.resize(600, 700)
    dlg.setStyleSheet("background-color: #1e1e2f; color: white;")

    layout = QVBoxLayout(dlg)
    layout.setSpacing(15)

    # Header Style
    lbl_style = "font-size: 16px; font-weight: bold; color: #00d2ff;"
    txt_style = "background-color: #2f2f40; color: #ccc; border: 1px solid #4a4a5e; font-family: monospace;"

    # Info Block
    info_lbl = QLabel(f"""
    <html>
    <body>
        <p><span style="color:#00d2ff;">Client:</span> {client}</p>
        <p><span style="color:#00d2ff;">Type:</span> {eng_type}</p>
        <p><span style="color:#00d2ff;">Deadline:</span> {deadline}</p>
        <p><span style="color:#888;">Path: {project_dir}</span></p>
    </body>
    </html>
    """)
    info_lbl.setTextFormat(Qt.RichText)
    layout.addWidget(info_lbl)

    # Domains Box
    layout.addWidget(QLabel("Target Domains:", styleSheet=lbl_style))
    txt_dom = QTextEdit()
    txt_dom.setPlainText(domains_text)
    txt_dom.setReadOnly(True)
    txt_dom.setStyleSheet(txt_style)
    layout.addWidget(txt_dom)

    # Scope Box
    layout.addWidget(QLabel("Scope / IP Ranges:", styleSheet=lbl_style))
    txt_scope = QTextEdit()
    txt_scope.setPlainText(scope_text)
    txt_scope.setReadOnly(True)
    txt_scope.setStyleSheet(txt_style)
    layout.addWidget(txt_scope)

    # Close Button
    btn_close = QPushButton("Close")
    btn_close.setStyleSheet("""
        QPushButton { background-color: #00d2ff; color: #1e1e2f; font-weight: bold; padding: 10px; border-radius: 5px; }
        QPushButton:hover { background-color: #3a7bd5; }
    """)
    btn_close.clicked.connect(dlg.accept)
    layout.addWidget(btn_close)

    dlg.exec_()