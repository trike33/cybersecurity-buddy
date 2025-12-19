import sqlite3
import os
import csv

def initialize_bruteforce_db(folder_path, db_filename="bruteforce_data.db"):
    db_path = os.path.join(folder_path, db_filename)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Table: Services
    c.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    # Table: Commands
    c.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER,
            tool_name TEXT,
            template TEXT,
            FOREIGN KEY(service_id) REFERENCES services(id)
        )
    ''')

    # Seed Data
    c.execute("SELECT count(*) FROM services")
    if c.fetchone()[0] == 0:
        services = ["SSH", "FTP", "RDP", "SMB", "Telnet", "MySQL", "PostgreSQL", "HTTP-Form"]
        for s in services:
            c.execute("INSERT INTO services (name) VALUES (?)", (s,))
            svc_id = c.lastrowid
            
            if s == "SSH":
                c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                          (svc_id, "Hydra", "hydra -l {USER} -P {PASS_FILE} ssh://{TARGET} -t 4"))
                c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                          (svc_id, "Medusa", "medusa -h {TARGET} -u {USER} -P {PASS_FILE} -M ssh"))
            elif s == "FTP":
                c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                          (svc_id, "Hydra", "hydra -l {USER} -P {PASS_FILE} ftp://{TARGET}"))
            elif s == "RDP":
                c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                          (svc_id, "Hydra", "hydra -l {USER} -P {PASS_FILE} rdp://{TARGET}"))
            elif s == "SMB":
                c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                          (svc_id, "Hydra", "hydra -l {USER} -P {PASS_FILE} smb://{TARGET}"))

    conn.commit()
    conn.close()
    return db_path

def get_services(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name FROM services ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows

def get_commands_for_service(db_path, service_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM commands WHERE service_id=?", (service_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# --- CRUD OPERATIONS ---

def get_all_commands_detailed(db_path):
    """Returns list of dicts with flattened service name for UI table."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT c.id, s.name as service, c.tool_name, c.template 
        FROM commands c 
        JOIN services s ON c.service_id = s.id 
        ORDER BY s.name, c.tool_name
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def add_command(db_path, service_name, tool_name, template):
    """Adds a command, creating the service if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        # 1. Ensure Service Exists
        # Use simple check instead of INSERT OR IGNORE to get ID reliably across sqlite versions
        c.execute("SELECT id FROM services WHERE name=?", (service_name,))
        row = c.fetchone()
        if row:
            svc_id = row[0]
        else:
            c.execute("INSERT INTO services (name) VALUES (?)", (service_name,))
            svc_id = c.lastrowid
        
        # 2. Insert Command
        c.execute("INSERT INTO commands (service_id, tool_name, template) VALUES (?, ?, ?)", 
                  (svc_id, tool_name, template))
        conn.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_command(db_path, command_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM commands WHERE id=?", (command_id,))
    conn.commit()
    conn.close()

def import_from_csv(db_path, csv_path):
    """
    Imports commands from CSV.
    Expected Headers: service, tool, template
    """
    if not os.path.exists(csv_path):
        return False, "File not found"
        
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Normalize headers (strip spaces, lowercase)
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
            
            required = {'service', 'tool', 'template'}
            if not required.issubset(set(reader.fieldnames)):
                return False, f"CSV missing columns. Required: {required}"
            
            count = 0
            for row in reader:
                s = row.get('service', '').strip()
                t = row.get('tool', '').strip()
                tmpl = row.get('template', '').strip()
                if s and t and tmpl:
                    add_command(db_path, s, t, tmpl)
                    count += 1
            return True, f"Imported {count} commands."
    except Exception as e:
        return False, str(e)