import sqlite3
import os
import csv

def _get_resources_db_path(provided_path=None):
    """
    Helper to resolve the path to resources/attack_vectors.db 
    if no specific path is provided.
    """
    if provided_path:
        return provided_path
        
    # Go up two levels from utils/ to root, then into resources/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resources_dir = os.path.join(base_dir, "resources")
    
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    return os.path.join(resources_dir, "attack_vectors.db")

def initialize_attack_db(db_path=None):
    """
    Initializes the attack vectors database in resources/ if needed.
    Also handles importing from a CSV if the DB is empty.
    """
    final_path = _get_resources_db_path(db_path)
    
    # Ensure directory exists
    db_dir = os.path.dirname(final_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    conn = sqlite3.connect(final_path)
    c = conn.cursor()
    
    # Create Table - ports is TEXT to support "80-8080"
    c.execute('''CREATE TABLE IF NOT EXISTS attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    ports TEXT NOT NULL,
                    attack_name TEXT NOT NULL,
                    auth_required INTEGER DEFAULT 0,
                    dangerous INTEGER DEFAULT 0
                )''')
    
    # Check if empty, if so try to seed from CSV
    c.execute("SELECT count(*) FROM attacks")
    if c.fetchone()[0] == 0:
        csv_path = os.path.join(os.path.dirname(final_path), "Attack_vectors.csv")
        # You can also look for the uploaded file name
        if not os.path.exists(csv_path):
             # Fallback check for the file you uploaded
             csv_path = os.path.join(os.path.dirname(final_path), "Attack_vectors - Full 1.csv")

        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    to_insert = []
                    for row in reader:
                        to_insert.append((
                            row.get('service', 'unknown'),
                            row.get('ports', '0'),
                            row.get('attack_name', 'Unknown Attack'),
                            int(row.get('auth_required', 0)),
                            int(row.get('dangerous', 0))
                        ))
                    
                    c.executemany("INSERT INTO attacks (service, ports, attack_name, auth_required, dangerous) VALUES (?, ?, ?, ?, ?)", to_insert)
                    print(f"[AttackDB] Seeded {len(to_insert)} vectors from CSV.")
            except Exception as e:
                print(f"[AttackDB] Error seeding from CSV: {e}")

    conn.commit()
    conn.close()
    return final_path

def get_all_vectors(db_path):
    """Returns all vectors as a list of dicts."""
    vectors = []
    if not os.path.exists(db_path):
        return vectors
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM attacks ORDER BY service")
        rows = c.fetchall()
        for row in rows:
            vectors.append(dict(row))
        conn.close()
    except Exception as e:
        print(f"[AttackDB] Error fetching vectors: {e}")
    return vectors

def get_vectors_for_port(db_path, port_str):
    """
    Finds vectors matching a specific port.
    Supports multi-port syntax like '80-8080-8000' or '80,8080'.
    """
    vectors = []
    service_name = "unknown"
    
    if not os.path.exists(db_path):
        return service_name, vectors

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 1. OPTIMIZATION: Use LIKE to filter candidates first.
        # This will return "8080" when searching for "80", which is fine (we filter later).
        # It prevents fetching the entire table every time.
        c.execute("SELECT * FROM attacks WHERE ports LIKE ?", (f"%{port_str}%",))
        rows = c.fetchall()
        
        target_port = str(port_str).strip()
        
        for row in rows:
            # row mapping: 0=id, 1=service, 2=ports, 3=name, 4=auth, 5=danger
            db_ports_raw = str(row[2])
            
            # 2. LOGIC FIX: Normalize and Split
            # Convert "80-8080" -> "80, 8080" -> list
            normalized_ports = db_ports_raw.replace('-', ',').replace(';', ',')
            valid_ports = [p.strip() for p in normalized_ports.split(',') if p.strip()]
            
            # 3. STRICT CHECK: Ensure exact match
            if target_port in valid_ports:
                if service_name == "unknown":
                    service_name = row[1]
                    
                vectors.append({
                    "id": row[0],
                    "name": row[3],
                    "service": row[1],
                    "auth": bool(row[4]),
                    "dangerous": bool(row[5])
                })
        
        conn.close()
    except Exception as e:
        print(f"[AttackDB] Error fetching vectors: {e}")
        
    return service_name, vectors