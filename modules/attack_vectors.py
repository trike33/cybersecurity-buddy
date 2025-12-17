import sys
import os
import sqlite3
from collections import defaultdict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QDialog, QHBoxLayout, QLabel, 
                             QTreeWidget, QTreeWidgetItem, QSplitter, QFrame,
                             QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QCheckBox, QStackedWidget)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient

# Import the DB utility for Attack Vector CRUD
from utils import attack_vectors_db

# ---------------------------------------------------------
# 1. DATABASE MANAGER DIALOG (CRUD UI)
#    (Unchanged from previous version)
# ---------------------------------------------------------
class DatabaseManagerDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Attack Vectors Database")
        self.setMinimumSize(800, 600)
        self.db_path = db_path
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QTableWidget { background-color: #2f2f40; gridline-color: #4a4a5e; color: #e0e0e0; }
            QHeaderView::section { background-color: #1e1e2f; color: white; padding: 4px; }
            QLineEdit { background-color: #222; color: #00d2ff; padding: 5px; border: 1px solid #555; }
            QPushButton { padding: 8px; background-color: #3e3e50; color: white; border: 1px solid #555; }
            QPushButton:hover { background-color: #4e4e60; border-color: #00d2ff; }
            QPushButton#DeleteBtn { background-color: #550000; border: 1px solid #770000; }
            QPushButton#DeleteBtn:hover { background-color: #770000; }
        """)

        layout = QVBoxLayout(self)

        # -- ADD NEW FORM --
        form_group = QFrame()
        form_group.setStyleSheet("background-color: #252535; border-radius: 5px; padding: 10px;")
        form_layout = QHBoxLayout(form_group)
        
        self.inp_service = QLineEdit()
        self.inp_service.setPlaceholderText("Service")
        self.inp_service.setFixedWidth(100)
        
        self.inp_ports = QLineEdit()
        self.inp_ports.setPlaceholderText("Ports (e.g. 445)")
        self.inp_ports.setFixedWidth(120)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Attack Name")
        
        self.chk_auth = QCheckBox("Auth Req")
        self.chk_danger = QCheckBox("Dangerous")
        
        btn_add = QPushButton("Add Vector")
        btn_add.clicked.connect(self.add_entry)

        form_layout.addWidget(self.inp_service)
        form_layout.addWidget(self.inp_ports)
        form_layout.addWidget(self.inp_name)
        form_layout.addWidget(self.chk_auth)
        form_layout.addWidget(self.chk_danger)
        form_layout.addWidget(btn_add)
        
        layout.addWidget(QLabel("<b>Add New Attack Vector:</b>"))
        layout.addWidget(form_group)

        # -- TABLE VIEW --
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Service", "Ports", "Attack Name", "Auth?", "Dangerous?"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers) 
        layout.addWidget(self.table)

        btn_del = QPushButton("Delete Selected Row")
        btn_del.setObjectName("DeleteBtn")
        btn_del.clicked.connect(self.delete_entry)
        layout.addWidget(btn_del)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        vectors = attack_vectors_db.get_all_vectors(self.db_path)
        for row_idx, v in enumerate(vectors):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(v['id'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(v['service']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(v['ports']))
            self.table.setItem(row_idx, 3, QTableWidgetItem(v['attack_name']))
            self.table.setItem(row_idx, 4, QTableWidgetItem("Yes" if v['auth_required'] else "No"))
            
            dang_str = "Yes" if v['dangerous'] else "No"
            item_dang = QTableWidgetItem(dang_str)
            if v['dangerous']: item_dang.setForeground(QColor("#ff4444"))
            self.table.setItem(row_idx, 5, item_dang)

    def add_entry(self):
        if attack_vectors_db.add_attack_vector(self.db_path, self.inp_service.text(), self.inp_ports.text(), 
                                               self.inp_name.text(), self.chk_auth.isChecked(), self.chk_danger.isChecked()):
            self.inp_name.clear()
            self.load_data()

    def delete_entry(self):
        if self.table.currentRow() >= 0:
            vid = self.table.item(self.table.currentRow(), 0).text()
            if QMessageBox.question(self, "Confirm", "Delete this vector?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                attack_vectors_db.delete_attack_vector(self.db_path, vid)
                self.load_data()

# ---------------------------------------------------------
# 2. DATA MANAGER
# ---------------------------------------------------------
class AttackDataManager:
    def __init__(self, project_folder, attack_db_path):
        self.project_folder = project_folder
        self.network_db_path = os.path.join(project_folder, "network_information.db")
        self.attack_db_path = attack_db_path
        
        # Ensure ATTACK DB exists (handled by utils)
        attack_vectors_db.initialize_attack_db(self.attack_db_path)
        
        # NOTE: We do NOT auto-create network DB anymore.
        # It is handled via the create_network_db method called by UI.

    def network_db_exists(self):
        return os.path.exists(self.network_db_path)

    def create_network_db(self):
        """
        Reads naabu_out and scope.txt to create network_information.db.
        """
        host_port_file = os.path.join(self.project_folder, "naabu_out")
        host_file = os.path.join(self.project_folder, "scope.txt")

        # Double check existence (safety)
        if not os.path.exists(host_port_file) or not os.path.exists(host_file):
            return False, "Missing input files (naabu_out or scope.txt)"

        host_ports = defaultdict(set)
        hosts = set()

        # Parse naabu_out
        try:
            with open(host_port_file, "r") as f:
                for line in f:
                    if ":" in line:
                        h, p = line.strip().split(":", 1)
                        host_ports[h].add(p)
        except Exception as e:
            return False, f"Error reading naabu_out: {e}"
        
        # Parse scope.txt
        try:
            with open(host_file, "r") as f:
                for line in f:
                    if line.strip(): 
                        hosts.add(line.strip())
        except Exception as e:
            return False, f"Error reading scope.txt: {e}"

        all_hosts = hosts.union(host_ports.keys())
        
        try:
            conn = sqlite3.connect(self.network_db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS hosts (host TEXT PRIMARY KEY, ports TEXT, live BOOLEAN)")
            
            for host in all_hosts:
                ports = ",".join(sorted(host_ports.get(host, [])))
                live = host in host_ports
                cur.execute("INSERT OR REPLACE INTO hosts VALUES (?, ?, ?)", (host, ports, live))
            
            conn.commit()
            conn.close()
            return True, "Database created successfully."
        except Exception as e:
            return False, f"Database error: {e}"

    def get_all_hosts(self):
        nodes = []
        if not self.network_db_exists(): return nodes
        try:
            conn = sqlite3.connect(self.network_db_path)
            c = conn.cursor()
            c.execute("SELECT host, ports, live FROM hosts")
            for r in c.fetchall():
                ports = [p for p in r[1].split(',') if p]
                nodes.append({
                    "ip": r[0], "ports": ports, "live": bool(r[2]),
                    "type": "Server" if len(ports) > 3 else "Client"
                })
            conn.close()
        except: pass
        return nodes

    def get_attack_info(self, port):
        return attack_vectors_db.get_vectors_for_port(self.attack_db_path, port)

# ---------------------------------------------------------
# 3. VISUALIZATION ITEMS (Unchanged)
# ---------------------------------------------------------
class NetworkNodeItem(QGraphicsItem):
    def __init__(self, node_data, callback):
        super().__init__()
        self.data = node_data
        self.callback = callback
        self.setAcceptHoverEvents(True)
        self.color_live = QColor("#00d2ff")
        self.color_dead = QColor("#444444")
        self.color_danger = QColor("#ff4444")

    def boundingRect(self):
        return QRectF(-40, -40, 80, 100)

    def paint(self, painter, option, widget):
        is_live = self.data['live']
        is_server = self.data['type'] == "Server"
        base_color = self.color_live if is_live else self.color_dead
        
        if is_live:
            grad = QRadialGradient(0, 0, 45)
            grad.setColorAt(0, QColor(0, 210, 255, 60))
            grad.setColorAt(1, QColor(0, 210, 255, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(-50, -50, 100, 100)

        painter.setPen(QPen(base_color, 2))
        painter.setBrush(QColor(30, 30, 40, 200) if is_live else QColor(30, 30, 30, 150))
        
        if is_server:
            painter.drawRect(-20, -25, 40, 50)
            painter.drawLine(-15, -10, 15, -10)
            painter.drawLine(-15, 5, 15, 5)
        else:
            painter.drawRect(-25, -20, 50, 35)
            painter.drawLine(-10, 15, 10, 15)

        painter.setPen(Qt.white if is_live else Qt.gray)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        painter.drawText(QRectF(-60, 35, 120, 20), Qt.AlignCenter, self.data['ip'])

        port_cnt = len(self.data['ports'])
        if port_cnt > 0:
            painter.setBrush(self.color_danger)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(20, -35, 18, 18)
            painter.setPen(Qt.white)
            painter.drawText(QRectF(20, -35, 18, 18), Qt.AlignCenter, str(port_cnt))

    def mousePressEvent(self, event):
        self.callback(self.data)

class NodeDetailsDialog(QDialog):
    def __init__(self, node_data, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Host Details: {node_data['ip']}")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QTreeWidget { background-color: #2f2f40; border: 1px solid #4a4a5e; color: #00d2ff; }
            QHeaderView::section { background-color: #1e1e2f; color: white; }
            QLabel { color: #e0e0e0; }
        """)
        
        self.node_data = node_data
        self.db_manager = db_manager

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        left_frame = QFrame()
        l_layout = QVBoxLayout(left_frame)
        
        lbl_ip = QLabel(node_data['ip'])
        lbl_ip.setFont(QFont("Arial", 22, QFont.Bold))
        lbl_ip.setStyleSheet("color: #00d2ff;")
        status = "Alive" if node_data['live'] else "Dead/Unreachable"
        lbl_stat = QLabel(f"Status: {status}")
        l_layout.addWidget(lbl_ip)
        l_layout.addWidget(lbl_stat)
        l_layout.addSpacing(15)
        l_layout.addWidget(QLabel("Open Ports & Detected Services:"))
        self.port_tree = QTreeWidget()
        self.port_tree.setHeaderLabels(["Port", "Service"])
        l_layout.addWidget(self.port_tree)
        splitter.addWidget(left_frame)

        right_frame = QFrame()
        r_layout = QVBoxLayout(right_frame)
        r_layout.addWidget(QLabel("Available Attack Vectors:"))
        self.vector_tree = QTreeWidget()
        self.vector_tree.setHeaderLabels(["Service/Port", "Attack Name", "Auth?", "Dangerous?"])
        r_layout.addWidget(self.vector_tree)
        splitter.addWidget(right_frame)
        
        layout.addWidget(splitter)
        splitter.setSizes([300, 600])
        self.populate_data()

    def populate_data(self):
        for port in self.node_data['ports']:
            service_name, vectors = self.db_manager.get_attack_info(port)
            p_item = QTreeWidgetItem(self.port_tree)
            p_item.setText(0, port)
            p_item.setText(1, service_name)
            
            if vectors:
                root_item = QTreeWidgetItem(self.vector_tree)
                root_item.setText(0, f"{service_name.upper()} ({port})")
                root_item.setExpanded(True)
                for v in vectors:
                    v_item = QTreeWidgetItem(root_item)
                    v_item.setText(1, v['name'])
                    v_item.setText(2, "Yes" if v['auth'] else "No")
                    v_item.setText(3, "True" if v['dangerous'] else "False")
                    if v['dangerous']: v_item.setForeground(3, QBrush(QColor("#ff4444")))

# ---------------------------------------------------------
# 4. MAIN WIDGET (With New Creation Logic)
# ---------------------------------------------------------
class AttackVectorsWidget(QWidget):
    def __init__(self, project_folder, attack_db_path, parent=None):
        super().__init__(parent)
        self.db_manager = AttackDataManager(project_folder, attack_db_path)
        
        # We use a Stack to switch between "Create DB" view and "Map" view
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # -- PAGE 1: CREATION PLACEHOLDER --
        self.page_create = QWidget()
        self.setup_create_page()
        self.stack.addWidget(self.page_create)
        
        # -- PAGE 2: MAP VIEW --
        self.page_map = QWidget()
        self.setup_map_page()
        self.stack.addWidget(self.page_map)
        
        # -- INITIAL STATE CHECK --
        self.check_database_state()

    def setup_create_page(self):
        """Builds the UI for when the DB is missing."""
        layout = QVBoxLayout(self.page_create)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        lbl_msg = QLabel("No Network Information Database Found")
        lbl_msg.setStyleSheet("font-size: 24px; font-weight: bold; color: #aaa;")
        
        self.lbl_status = QLabel("Checking files...")
        self.lbl_status.setStyleSheet("font-size: 16px; color: #666;")
        
        self.btn_create = QPushButton("Create Database from Scan Files")
        self.btn_create.setFixedSize(300, 50)
        self.btn_create.setStyleSheet("""
            QPushButton { background-color: #00d2ff; color: #1e1e2f; font-weight: bold; border-radius: 5px; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        self.btn_create.clicked.connect(self.create_db)
        
        btn_check = QPushButton("Check Files Again")
        btn_check.setFixedSize(200, 40)
        btn_check.clicked.connect(self.check_files_availability)
        
        layout.addWidget(lbl_msg, alignment=Qt.AlignCenter)
        layout.addWidget(self.lbl_status, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_create, alignment=Qt.AlignCenter)
        layout.addWidget(btn_check, alignment=Qt.AlignCenter)

    def setup_map_page(self):
        """Builds the actual Graph UI."""
        layout = QVBoxLayout(self.page_map)
        layout.setContentsMargins(0,0,0,0)

        # Toolbar
        h_ctrl = QHBoxLayout()
        h_ctrl.setContentsMargins(10, 10, 10, 10)
        
        btn_db = QPushButton("⚙ Manage Attack DB")
        btn_db.setStyleSheet("""
            QPushButton { background-color: #2f2f40; border: 1px solid #00d2ff; color: #00d2ff; border-radius: 4px; padding: 6px; }
            QPushButton:hover { background-color: #00d2ff; color: #1e1e2f; }
        """)
        btn_db.clicked.connect(self.open_attack_db_manager)
        
        btn_refresh = QPushButton("↻ Refresh Map")
        btn_refresh.clicked.connect(self.refresh_map_view)
        
        # New: Re-Scan Button (To delete network DB and go back to create page)
        btn_reset = QPushButton("✖ Reset Network Info")
        btn_reset.setStyleSheet("color: #ff4444; border: 1px solid #550000; padding: 6px; background-color: #2f2f40;")
        btn_reset.clicked.connect(self.reset_network_db)

        h_ctrl.addWidget(QLabel("<b>Network Visualization</b>"))
        h_ctrl.addStretch()
        h_ctrl.addWidget(btn_reset)
        h_ctrl.addWidget(btn_db)
        h_ctrl.addWidget(btn_refresh)
        
        layout.addLayout(h_ctrl)
        
        # Graphics View
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background-color: #12121e; border: none;")
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view)

    # --- LOGIC ---

    def check_database_state(self):
        """Decides which page to show based on DB existence."""
        if self.db_manager.network_db_exists():
            self.stack.setCurrentWidget(self.page_map)
            self.refresh_map_view()
        else:
            self.stack.setCurrentWidget(self.page_create)
            self.check_files_availability()

    def check_files_availability(self):
        """Checks if scope.txt and naabu_out exist to enable the Create button."""
        p_folder = self.db_manager.project_folder
        f1 = os.path.join(p_folder, "scope.txt")
        f2 = os.path.join(p_folder, "naabu_out")
        
        has_scope = os.path.exists(f1)
        has_naabu = os.path.exists(f2)
        
        if has_scope and has_naabu:
            self.btn_create.setEnabled(True)
            self.lbl_status.setText("Files found: <span style='color:#00ff00'>scope.txt, naabu_out</span>")
            self.lbl_status.setTextFormat(Qt.RichText)
        else:
            self.btn_create.setEnabled(False)
            missing = []
            if not has_scope: missing.append("scope.txt")
            if not has_naabu: missing.append("naabu_out")
            self.lbl_status.setText(f"Missing files: <span style='color:#ff4444'>{', '.join(missing)}</span>")
            self.lbl_status.setTextFormat(Qt.RichText)

    def create_db(self):
        success, msg = self.db_manager.create_network_db()
        if success:
            QMessageBox.information(self, "Success", "Database created!")
            self.check_database_state()
        else:
            QMessageBox.critical(self, "Error", msg)

    def reset_network_db(self):
        """Deletes the current network DB file to allow regeneration."""
        confirm = QMessageBox.question(self, "Reset", "Delete current network map and regenerate from files?", 
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                if os.path.exists(self.db_manager.network_db_path):
                    os.remove(self.db_manager.network_db_path)
                self.check_database_state()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete DB file: {e}")

    def refresh_map_view(self):
        self.scene.clear()
        nodes = self.db_manager.get_all_hosts()
        
        if not nodes:
            # Should conceptually not happen if we are on this page, but good safety
            txt = self.scene.addText("Database is empty.")
            txt.setDefaultTextColor(Qt.white)
            return

        x_start, y_start = 50, 50
        gap = 160
        cols = 5
        
        for i, node in enumerate(nodes):
            item = NetworkNodeItem(node, self.open_details)
            item.setPos(x_start + (i%cols)*gap, y_start + (i//cols)*gap)
            self.scene.addItem(item)
        
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def open_details(self, node_data):
        dlg = NodeDetailsDialog(node_data, self.db_manager, self)
        dlg.exec_()

    def open_attack_db_manager(self):
        dlg = DatabaseManagerDialog(self.db_manager.attack_db_path, self)
        dlg.exec_()