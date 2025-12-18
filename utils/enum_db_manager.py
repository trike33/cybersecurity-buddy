import sqlite3
import csv
import os

class EnumDBManager:
    """
    Manages the enumeration database located in resources/.
    """
    def __init__(self, db_path=None):
        # Determine default path: ../resources/enumeration.db relative to this file
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resources_dir = os.path.join(base_dir, "resources")
            
            if not os.path.exists(resources_dir):
                os.makedirs(resources_dir)
                
            self.db_path = os.path.join(resources_dir, "enumeration.db")
        else:
            self.db_path = db_path
            
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Creates the commands table if it doesn't exist."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS enum_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                command TEXT,
                auth INTEGER DEFAULT 0,
                sudo INTEGER DEFAULT 0,
                service TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def is_empty(self):
        """Checks if the database is empty."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM enum_commands")
        count = c.fetchone()[0]
        conn.close()
        return count == 0

    def import_from_csv(self, csv_file_path):
        """
        Populates the database from a CSV file.
        """
        if not os.path.exists(csv_file_path):
            return False, "CSV file not found."

        try:
            conn = self._get_connection()
            c = conn.cursor()
            
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                required_headers = {'title', 'command', 'auth', 'sudo', 'service'}
                if not required_headers.issubset(set(reader.fieldnames)):
                    return False, f"CSV missing required columns: {required_headers - set(reader.fieldnames)}"

                rows_to_insert = []
                for row in reader:
                    rows_to_insert.append((
                        row['title'],
                        row['command'],
                        int(row['auth']),
                        int(row['sudo']),
                        row['service']
                    ))
                
                c.executemany('''
                    INSERT INTO enum_commands (title, command, auth, sudo, service) 
                    VALUES (?, ?, ?, ?, ?)
                ''', rows_to_insert)
            
            conn.commit()
            conn.close()
            return True, f"Successfully imported {len(rows_to_insert)} commands."

        except Exception as e:
            return False, f"Error importing CSV: {str(e)}"

    def get_services(self):
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT service FROM enum_commands ORDER BY service ASC")
        services = [row[0] for row in c.fetchall()]
        conn.close()
        return services

    def get_commands(self, service, auth_filter=None, sudo_filter=None):
        conn = self._get_connection()
        c = conn.cursor()
        
        query = "SELECT id, title, command, auth, sudo, service FROM enum_commands WHERE service = ?"
        params = [service]

        if auth_filter is not None:
            query += " AND auth = ?"
            params.append(auth_filter)
        
        if sudo_filter is not None:
            query += " AND sudo = ?"
            params.append(sudo_filter)

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        return [
            {"id": r[0], "title": r[1], "command": r[2], "auth": r[3], "sudo": r[4], "service": r[5]} 
            for r in rows
        ]