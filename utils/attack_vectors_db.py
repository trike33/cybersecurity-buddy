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
    """
    final_path = _get_resources_db_path(db_path)
    
    # Ensure directory exists (redundant if using helper, but good for safety)
    db_dir = os.path.dirname(final_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    conn = sqlite3.connect(final_path)
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
    
    # Check if empty, maybe seed default data if available
    c.execute("SELECT count(*) FROM attacks")
    if c.fetchone()[0] == 0:
        # Check for a default csv in utils to seed from
        seed_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attacks.csv")
        if os.path.exists(seed_csv):
            import_from_csv(final_path, seed_csv)
            print(f"[AttackDB] Seeded database from {seed_csv}")
        
    conn.commit()
    conn.close()
    return final_path

def import_from_csv(db_path, csv_path):
    """
    Imports attack vectors from a CSV file.
    Expected headers: service, ports, attack_name, auth_required, dangerous
    Returns: (bool_success, message)
    """
    if not os.path.exists(csv_path):
        return False, "CSV file not found."

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Normalize headers (strip whitespace)
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            
            required = {'service', 'ports', 'attack_name', 'auth_required', 'dangerous'}
            if not required.issubset(set(reader.fieldnames)):
                missing = required - set(reader.fieldnames)
                return False, f"CSV missing columns: {missing}"

            rows_to_insert = []
            for row in reader:
                rows_to_insert.append((
                    row['service'],
                    row['ports'],
                    row['attack_name'],
                    int(row.get('auth_required', 0)),
                    int(row.get('dangerous', 0))
                ))

            c.executemany("""
                INSERT INTO attacks (service, ports, attack_name, auth_required, dangerous) 
                VALUES (?, ?, ?, ?, ?)
            """, rows_to_insert)
            
        conn.commit()
        conn.close()
        return True, f"Successfully imported {len(rows_to_insert)} vectors."
        
    except Exception as e:
        return False, f"Import Error: {e}"

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
    """Finds vectors matching a specific port."""
    vectors = []
    service_name = "unknown"
    
    if not os.path.exists(db_path):
        return service_name, vectors

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM attacks WHERE ports LIKE ?", (f"%{port_str}%",))
        rows = c.fetchall()
        
        for row in rows:
            # Row mapping: 0=id, 1=service, 2=ports, 3=name, 4=auth, 5=danger
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