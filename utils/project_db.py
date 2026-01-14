import sqlite3
import os
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, 
                             QMessageBox, QLineEdit, QDateEdit, QHBoxLayout, QFormLayout, 
                             QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QDate

def initialize_project_db(folder_path, db_filename="project_data.db"):
    """Creates the SQLite DB and tables in the specified folder."""
    db_path = os.path.join(folder_path, db_filename)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Project Metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            engagement_type TEXT,
            deadline TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Scope / Domains
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,
            in_scope BOOLEAN DEFAULT 1
        )
    ''')

    # 3. Credentials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            description TEXT,
            host TEXT,
            service TEXT
        )
    ''')
    try: cursor.execute("ALTER TABLE credentials ADD COLUMN host TEXT"); 
    except: pass 
    try: cursor.execute("ALTER TABLE credentials ADD COLUMN service TEXT"); 
    except: pass

    # 4. Enumeration Tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT,
            port TEXT,
            service TEXT,
            completed BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 5. NEW: Progress Tracking (High Level Steps)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            step TEXT PRIMARY KEY,
            kind TEXT,
            completed BOOLEAN DEFAULT 0
        )
    ''')

    # Seed Default Progress Steps if empty
    cursor.execute("SELECT count(*) FROM progress")
    if cursor.fetchone()[0] == 0:
        steps = [
            ("Basic HTTP Check", "recon", 0),
            ("Naabu Scan", "recon", 0),
            ("Nmap TCP Scan", "recon", 0),
            ("Nmap UDP Scan", "recon", 0)
        ]
        cursor.executemany("INSERT INTO progress (step, kind, completed) VALUES (?, ?, ?)", steps)

    conn.commit()
    conn.close()
    return db_path

def save_project_details(db_path, client, eng_type, deadline, domain_list):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO project_info (client_name, engagement_type, deadline) VALUES (?, ?, ?)",
              (client, eng_type, deadline))
    for d in domain_list:
        clean_d = d.strip()
        if clean_d:
            c.execute("INSERT INTO domains (domain) VALUES (?)", (clean_d,))
    conn.commit()
    conn.close()

def update_project_metadata(db_path, client_name, deadline):
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
    if not os.path.exists(db_path): return False
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM domains")
        domain_list = [d.strip() for d in domains_text.splitlines() if d.strip()]
        for d in domain_list:
            c.execute("INSERT INTO domains (domain) VALUES (?)", (d,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating domains: {e}")
        return False

# --- CREDENTIALS CRUD ---
def add_credential(db_path, username, password, host="", service="", description=""):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO credentials (username, password, host, service, description) VALUES (?, ?, ?, ?, ?)", 
              (username, password, host, service, description))
    conn.commit()
    conn.close()

def delete_credential(db_path, cred_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM credentials WHERE id=?", (cred_id,))
    conn.commit()
    conn.close()

def get_credentials(db_path):
    if not os.path.exists(db_path): return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM credentials")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def load_project_data(db_path):
    data = {}
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM project_info ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        data['client_name'] = row['client_name']
        data['engagement_type'] = row['engagement_type']
        data['deadline'] = row['deadline']
    
    c.execute("SELECT domain FROM domains")
    domains = [r['domain'] for r in c.fetchall()]
    data['domains'] = domains

    # Load Creds
    c.execute("SELECT * FROM credentials")
    data['credentials'] = [dict(r) for r in c.fetchall()]

    conn.close()
    return data

def is_valid_project_db(db_path):
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

def get_hosts_for_service(db_path, service):
    """Returns a list of hosts that have the specific service open."""
    if not os.path.exists(db_path): return []
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Case-insensitive matching might be safer depending on how data was entered
    c.execute("SELECT host FROM enum WHERE service=? COLLATE NOCASE", (service,))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return list(set(rows)) # Return unique hosts

# --- ENUMERATION TRACKING ---

def sync_enum_data(db_path, data_list, completed_step=None):
    if not os.path.exists(db_path): return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    for item in data_list:
        # 1. Handle dynamic port ranges (e.g. "80-8080-8000" or "80,8080")
        raw_port = str(item['port'])
        normalized_ports = raw_port.replace('-', ',')
        port_list = [p.strip() for p in normalized_ports.split(',') if p.strip()]

        for single_port in port_list:
            # 2. Check and Insert each port individually
            c.execute("SELECT id FROM enum WHERE host=? AND port=?", (item['host'], single_port))
            if not c.fetchone():
                c.execute("INSERT INTO enum (host, port, service) VALUES (?, ?, ?)", 
                          (item['host'], single_port, item['service']))

    # 3. Update Progress (For the Ringing Bell feature)
    if completed_step:
        try:
            c.execute("UPDATE progress SET completed=1 WHERE step=?", (completed_step,))
        except Exception as e:
            print(f"Error updating progress: {e}")

    conn.commit(); conn.close()

def enum_record_exists(db_path, host, service):
    if not os.path.exists(db_path): return False
    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute("SELECT 1 FROM enum WHERE host=? AND service=?", (host, service))
    res = c.fetchone(); conn.close(); return res is not None

def set_enum_status(db_path, host, service, completed):
    if not os.path.exists(db_path): return
    conn = sqlite3.connect(db_path); c = conn.cursor(); val = 1 if completed else 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE enum SET completed=?, timestamp=? WHERE host=? AND service=?", (val, now, host, service))
    conn.commit(); conn.close()

def get_enum_status(db_path, host, service):
    if not os.path.exists(db_path): return False
    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute("SELECT completed FROM enum WHERE host=? AND service=?", (host, service))
    row = c.fetchone(); conn.close(); return bool(row[0]) if row else False

def get_unique_services(db_path):
    if not os.path.exists(db_path): return []
    conn = sqlite3.connect(db_path); c = conn.cursor()
    c.execute("SELECT DISTINCT service FROM enum ORDER BY service ASC")
    rows = [r[0] for r in c.fetchall() if r[0]]; conn.close(); return rows


# --- PROGRESS & DASHBOARD HELPERS ---

def mark_step_complete(db_path, step_name, completed=True):
    """Marks a high-level step (Naabu, Nmap) as complete."""
    if not os.path.exists(db_path): return
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    val = 1 if completed else 0
    c.execute("UPDATE progress SET completed=? WHERE step=?", (val, step_name))
    conn.commit()
    conn.close()

def get_dashboard_stats(db_path):
    """Aggregates all data for the dashboard."""
    stats = {
        "client": "Unknown", "type": "Pentest", "deadline": "",
        "scope_count": 0, "creds_count": 0,
        "recon_steps": [], "enum_services": [],
        "overall_progress": 0
    }
    
    if not os.path.exists(db_path): return stats
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Info
    c.execute("SELECT * FROM project_info ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        stats["client"] = row["client_name"]
        stats["type"] = row["engagement_type"]
        stats["deadline"] = row["deadline"]

    # 2. Counts
    c.execute("SELECT count(*) FROM domains")
    stats["scope_count"] = c.fetchone()[0]
    
    c.execute("SELECT count(*) FROM credentials")
    stats["creds_count"] = c.fetchone()[0]

    # 3. Recon Progress
    c.execute("SELECT step, completed FROM progress WHERE kind='recon'")
    stats["recon_steps"] = [dict(r) for r in c.fetchall()]

    # 4. Enumeration Progress (Aggregated by Service)
    # We want to see how many services of each type are completed
    # e.g. SSH: 2/5 completed
    c.execute("SELECT service, count(*) as total, sum(completed) as done FROM enum GROUP BY service")
    svc_rows = c.fetchall()
    
    total_tasks = len(stats["recon_steps"])
    done_tasks = sum(1 for x in stats["recon_steps"] if x['completed'])
    
    for r in svc_rows:
        svc_name = r['service']
        total = r['total']
        done = r['done'] if r['done'] else 0
        stats["enum_services"].append({
            "name": svc_name,
            "total": total,
            "done": done,
            "percent": int((done/total)*100) if total > 0 else 0
        })
        
        # Add to overall calculation
        total_tasks += total
        done_tasks += done

    stats["overall_progress"] = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    conn.close()
    return stats

# ---------------------------------------------------------
# EDITOR DIALOG
# ---------------------------------------------------------
class ProjectEditDialog(QDialog):
    def __init__(self, parent, db_path):
        super().__init__(parent)
        self.db_path = db_path
        self.project_dir = os.path.dirname(db_path)
        self.setWindowTitle("Edit Project Settings")
        self.resize(750, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QLabel { font-size: 14px; color: #e0e0e0; font-weight: bold; }
            QLineEdit, QDateEdit, QTextEdit, QTableWidget { 
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
            QTabWidget::pane { border: 1px solid #4a4a5e; }
            QTabBar::tab { background: #2f2f40; color: #aaa; padding: 8px 20px; }
            QTabBar::tab:selected { background: #00d2ff; color: #1e1e2f; font-weight: bold; }
        """)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # TAB 1: GENERAL
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        meta_layout = QFormLayout()
        self.inp_client = QLineEdit()
        self.inp_deadline = QDateEdit()
        self.inp_deadline.setCalendarPopup(True)
        self.inp_deadline.setDisplayFormat("yyyy-MM-dd")
        meta_layout.addRow("Client Name:", self.inp_client)
        meta_layout.addRow("Deadline:", self.inp_deadline)
        gen_layout.addLayout(meta_layout)
        gen_layout.addWidget(QLabel("Target Domains (domains.txt):"))
        self.txt_domains = QTextEdit()
        gen_layout.addWidget(self.txt_domains)
        gen_layout.addWidget(QLabel("Scope / IP Ranges (scope.txt):"))
        self.txt_scope = QTextEdit()
        gen_layout.addWidget(self.txt_scope)
        self.tabs.addTab(tab_general, "General Info")

        # TAB 2: CREDENTIALS
        tab_creds = QWidget()
        cred_layout = QVBoxLayout(tab_creds)
        form_cred = QHBoxLayout()
        self.cred_host = QLineEdit(); self.cred_host.setPlaceholderText("Host (IP/Domain)")
        self.cred_service = QLineEdit(); self.cred_service.setPlaceholderText("Service (e.g. smb, ssh)")
        self.cred_user = QLineEdit(); self.cred_user.setPlaceholderText("Username")
        self.cred_pass = QLineEdit(); self.cred_pass.setPlaceholderText("Password")
        btn_add_cred = QPushButton("Add"); btn_add_cred.setFixedWidth(80); btn_add_cred.clicked.connect(self.add_cred_handler)
        form_cred.addWidget(self.cred_host); form_cred.addWidget(self.cred_service); form_cred.addWidget(self.cred_user); form_cred.addWidget(self.cred_pass); form_cred.addWidget(btn_add_cred)
        cred_layout.addLayout(form_cred)
        self.table_creds = QTableWidget()
        self.table_creds.setColumnCount(5)
        self.table_creds.setHorizontalHeaderLabels(["ID", "Host", "Service", "Username", "Password"])
        self.table_creds.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_creds.setSelectionBehavior(QTableWidget.SelectRows)
        cred_layout.addWidget(self.table_creds)
        btn_del_cred = QPushButton("Delete Selected Credential"); btn_del_cred.clicked.connect(self.del_cred_handler)
        cred_layout.addWidget(btn_del_cred)
        self.tabs.addTab(tab_creds, "Credentials")

        # BUTTONS
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save All Changes"); btn_save.setObjectName("SaveBtn"); btn_save.clicked.connect(self.save_changes)
        btn_layout.addStretch(); btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def load_data(self):
        data = load_project_data(self.db_path)
        if data:
            self.inp_client.setText(data.get('client_name', ''))
            d_str = data.get('deadline', '')
            if d_str: self.inp_deadline.setDate(QDate.fromString(d_str, "yyyy-MM-dd"))
            else: self.inp_deadline.setDate(QDate.currentDate())
        dom_file = os.path.join(self.project_dir, "domains.txt")
        if os.path.exists(dom_file):
            with open(dom_file, 'r', encoding='utf-8') as f: self.txt_domains.setPlainText(f.read())
        scope_file = os.path.join(self.project_dir, "scope.txt")
        if os.path.exists(scope_file):
            with open(scope_file, 'r', encoding='utf-8') as f: self.txt_scope.setPlainText(f.read())
        self.refresh_creds_table()

    def refresh_creds_table(self):
        self.table_creds.setRowCount(0)
        creds = get_credentials(self.db_path)
        for i, c in enumerate(creds):
            self.table_creds.insertRow(i)
            self.table_creds.setItem(i, 0, QTableWidgetItem(str(c['id'])))
            self.table_creds.setItem(i, 1, QTableWidgetItem(c.get('host', '')))
            self.table_creds.setItem(i, 2, QTableWidgetItem(c.get('service', '')))
            self.table_creds.setItem(i, 3, QTableWidgetItem(c['username']))
            self.table_creds.setItem(i, 4, QTableWidgetItem(c['password']))

    def add_cred_handler(self):
        h = self.cred_host.text().strip(); s = self.cred_service.text().strip(); u = self.cred_user.text().strip(); p = self.cred_pass.text().strip()
        if u and p:
            add_credential(self.db_path, u, p, host=h, service=s)
            self.cred_user.clear(); self.cred_pass.clear(); self.refresh_creds_table()
        else: QMessageBox.warning(self, "Missing Info", "Username and Password are required.")

    def del_cred_handler(self):
        row = self.table_creds.currentRow()
        if row >= 0:
            cid = self.table_creds.item(row, 0).text()
            delete_credential(self.db_path, cid)
            self.refresh_creds_table()

    def save_changes(self):
        new_client = self.inp_client.text().strip(); new_deadline = self.inp_deadline.date().toString("yyyy-MM-dd")
        if not new_client: QMessageBox.warning(self, "Error", "Client Name cannot be empty."); return
        update_project_metadata(self.db_path, new_client, new_deadline)
        update_project_domains(self.db_path, self.txt_domains.toPlainText())
        try:
            with open(os.path.join(self.project_dir, "domains.txt"), 'w', encoding='utf-8') as f: f.write(self.txt_domains.toPlainText())
            with open(os.path.join(self.project_dir, "scope.txt"), 'w', encoding='utf-8') as f: f.write(self.txt_scope.toPlainText())
        except Exception as e: QMessageBox.critical(self, "File Error", f"Failed to write files: {str(e)}"); return
        QMessageBox.information(self, "Success", "Project updated.")
        self.accept()
