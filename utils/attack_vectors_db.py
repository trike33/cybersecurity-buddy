import sqlite3
import os

def initialize_attack_db(db_path):
    """
    Initializes the attack vectors database.
    If it doesn't exist, it creates the table and seeds it with common defaults.
    """
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create Table
    c.execute('''CREATE TABLE IF NOT EXISTS attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    ports TEXT NOT NULL,
                    attack_name TEXT NOT NULL,
                    auth_required INTEGER DEFAULT 0,
                    dangerous INTEGER DEFAULT 0
                )''')
    
    # Check if empty, then seed
    c.execute("SELECT count(*) FROM attacks")
    if c.fetchone()[0] == 0:
        seed_data = [
            # (service, ports, name, auth, dangerous)
            ("smb", "445", "EternalBlue (MS17-010)", 0, 1),
            ("smb", "445,139", "SMB Null Session", 0, 0),
            ("smb", "445", "SMB Signing Disabled", 0, 0),
            ("http", "80,443,8080,8000", "SQL Injection (General)", 0, 1),
            ("http", "80,443", "Slowloris DoS", 0, 1),
            ("ftp", "21", "Anonymous Login", 0, 0),
            ("ssh", "22", "SSH Brute Force", 0, 1),
            ("rdp", "3389", "BlueKeep (CVE-2019-0708)", 0, 1),
            ("telnet", "23", "Cleartext Credentials", 0, 0),
            ("mysql", "3306", "MySQL Default Creds", 0, 0),
            ("dns", "53", "DNS Zone Transfer", 0, 0)
        ]
        c.executemany("INSERT INTO attacks (service, ports, attack_name, auth_required, dangerous) VALUES (?,?,?,?,?)", seed_data)
        print(f"[AttackDB] Database initialized and seeded at {db_path}")
        
    conn.commit()
    conn.close()

def add_attack_vector(db_path, service, ports, name, auth, dangerous):
    """Adds a new attack vector to the DB."""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("INSERT INTO attacks (service, ports, attack_name, auth_required, dangerous) VALUES (?, ?, ?, ?, ?)",
                  (service, ports, name, 1 if auth else 0, 1 if dangerous else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[AttackDB] Error adding vector: {e}")
        return False

def delete_attack_vector(db_path, vector_id):
    """Deletes an attack vector by ID."""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM attacks WHERE id=?", (vector_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[AttackDB] Error deleting vector: {e}")
        return False

def get_all_vectors(db_path):
    """Returns all vectors as a list of dicts."""
    vectors = []
    if not os.path.exists(db_path):
        return vectors
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Allows accessing columns by name
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
    Matches if the DB 'ports' column contains the target port string.
    """
    vectors = []
    service_name = "unknown"
    
    if not os.path.exists(db_path):
        return service_name, vectors

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # We search for the port number (e.g., '445') inside the comma-separated DB string (e.g., '139,445')
        # Using simple string matching for 'LIKE %port%'
        c.execute("SELECT * FROM attacks WHERE ports LIKE ?", (f"%{port_str}%",))
        rows = c.fetchall()
        
        for row in rows:
            # Row index: 0=id, 1=service, 2=ports, 3=name, 4=auth, 5=danger
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
        print(f"[AttackDB] Error querying port {port_str}: {e}")
        
    return service_name, vectors
