import sys
import os
import sqlite3
import math
from collections import defaultdict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QDialog, QHBoxLayout, QLabel, 
                             QTreeWidget, QTreeWidgetItem, QSplitter, QFrame,
                             QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QCheckBox, QStackedWidget, QGraphicsLineItem, QScrollArea, QComboBox, QSizePolicy)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, QPolygonF

# Import the DB utility
from utils import attack_vectors_db

# ---------------------------------------------------------
# 1. CUSTOM GRAPHICS COMPONENTS
# ---------------------------------------------------------

class ZoomableGraphicsView(QGraphicsView):
    """A GraphicsView that supports wheel zooming and panning."""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setStyleSheet("background-color: #12121e; border: none;")
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        """Handle zoom in/out with Ctrl key, or standard scroll."""
        # Optional: Require Ctrl key for zoom to avoid interfering with normal scrolling
        # If you want always-on zoom, remove the modifiers check.
        if event.modifiers() & Qt.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            super().wheelEvent(event)

class ConnectionEdge(QGraphicsLineItem):
    """A dynamic line connecting two nodes."""
    def __init__(self, source_node, dest_node):
        super().__init__()
        self.source = source_node
        self.dest = dest_node
        self.setZValue(-1) # Draw behind nodes
        
        pen = QPen(QColor("#444444"), 2)
        pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        
        # Register with nodes
        self.source.add_edge(self)
        self.dest.add_edge(self)
        self.adjust()

    def adjust(self):
        """Recalculate line position based on node centers."""
        if not self.source or not self.dest: return
        line = QLineF(self.source.scenePos(), self.dest.scenePos())
        self.setLine(line)

class NetworkNodeItem(QGraphicsItem):
    """The interactive host node (Computer/Server)."""
    def __init__(self, node_data, callback):
        super().__init__()
        self.data = node_data
        self.callback = callback
        self.edges = []
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        self.color_live = QColor("#00d2ff")
        self.color_dead = QColor("#555555")
        self.color_danger = QColor("#ff4444")

    def add_edge(self, edge):
        self.edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.adjust()
        return super().itemChange(change, value)

    def boundingRect(self):
        return QRectF(-40, -40, 80, 80)

    def paint(self, painter, option, widget):
        is_live = self.data.get('live', False)
        is_server = self.data.get('type') == "Server"
        base_color = self.color_live if is_live else self.color_dead
        
        # Glow
        if is_live:
            grad = QRadialGradient(0, 0, 40)
            grad.setColorAt(0, QColor(0, 210, 255, 60))
            grad.setColorAt(1, QColor(0, 210, 255, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(-45, -45, 90, 90)

        # Icon Shape
        painter.setPen(QPen(base_color, 2))
        painter.setBrush(QColor(30, 30, 40, 230) if is_live else QColor(30, 30, 30, 150))
        
        if is_server:
            painter.drawRect(-15, -20, 30, 40)
            painter.drawLine(-10, -10, 10, -10)
            painter.drawLine(-10, 0, 10, 0)
            painter.drawLine(-10, 10, 10, 10)
        else:
            painter.drawRect(-20, -15, 40, 30)
            painter.drawLine(-10, 15, 10, 15)
            painter.drawLine(-15, 20, 15, 20)

        # IP Label
        painter.setPen(Qt.white if is_live else Qt.gray)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRectF(-50, 25, 100, 20), Qt.AlignCenter, self.data['ip'])

        # Port Badge
        ports = self.data.get('ports', [])
        if ports:
            painter.setBrush(self.color_danger)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(15, -30, 16, 16)
            painter.setPen(Qt.white)
            painter.drawText(QRectF(15, -30, 16, 16), Qt.AlignCenter, str(len(ports)))

    def mouseDoubleClickEvent(self, event):
        self.callback(self.data)
        super().mouseDoubleClickEvent(event)

# ---------------------------------------------------------
# NEW: NOTEBOOK-STYLE CARD WIDGET
# ---------------------------------------------------------
class AttackVectorCard(QFrame):
    """A stylish card representing a single attack vector."""
    def __init__(self, vector_data, port):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            AttackVectorCard {
                background-color: #2a2a3b;
                border: 1px solid #3e3e50;
                border-radius: 8px;
                margin-bottom: 8px;
            }
            QLabel#Title { font-size: 16px; font-weight: bold; color: #00d2ff; }
            QLabel#Service { font-size: 12px; font-weight: bold; color: #aaa; }
            QLabel#TagDanger { background-color: #550000; color: #ffcccc; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagSafe { background-color: #224422; color: #ccffcc; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagAuth { background-color: #554400; color: #ffddaa; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagNoAuth { background-color: #004444; color: #ccffff; border-radius: 4px; padding: 4px; font-size: 11px; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header: Service & Port
        lbl_service = QLabel(f"{vector_data['service'].upper()} (Port {port})")
        lbl_service.setObjectName("Service")
        layout.addWidget(lbl_service)
        
        # Body: Attack Name
        lbl_title = QLabel(vector_data['name'])
        lbl_title.setObjectName("Title")
        lbl_title.setWordWrap(True)
        layout.addWidget(lbl_title)
        
        # Footer: Tags
        tag_layout = QHBoxLayout()
        tag_layout.setSpacing(10)
        
        # Dangerous Tag
        if vector_data['dangerous']:
            lbl_danger = QLabel("DANGEROUS")
            lbl_danger.setObjectName("TagDanger")
            tag_layout.addWidget(lbl_danger)
        else:
            lbl_safe = QLabel("Safe Check")
            lbl_safe.setObjectName("TagSafe")
            tag_layout.addWidget(lbl_safe)

        # Auth Tag
        if vector_data['auth']:
            lbl_auth = QLabel("AUTH REQ")
            lbl_auth.setObjectName("TagAuth")
            tag_layout.addWidget(lbl_auth)
        else:
            lbl_no_auth = QLabel("NO AUTH")
            lbl_no_auth.setObjectName("TagNoAuth")
            tag_layout.addWidget(lbl_no_auth)
            
        tag_layout.addStretch()
        layout.addLayout(tag_layout)

class SubnetHubItem(QGraphicsItem):
    """A visual anchor for a subnet."""
    def __init__(self, subnet_name):
        super().__init__()
        self.subnet_name = subnet_name
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.edges = []

    def add_edge(self, edge):
        self.edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.adjust()
        return super().itemChange(change, value)

    def boundingRect(self):
        return QRectF(-30, -30, 60, 60)

    def paint(self, painter, option, widget):
        # Switch/Cloud Icon
        painter.setPen(QPen(QColor("#8888aa"), 2))
        painter.setBrush(QColor(40, 40, 60, 200))
        painter.drawEllipse(-25, -12, 50, 24) 
        painter.setPen(QColor("#aaaaaa"))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QRectF(-40, 15, 80, 20), Qt.AlignCenter, self.subnet_name)

# ---------------------------------------------------------
# 2. DIALOGS (Details & DB Management)
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
            QLineEdit { background-color: #222; color: #00d2ff; padding: 5px; border: 1px solid #555; }
            QPushButton { padding: 8px; background-color: #3e3e50; color: white; border: 1px solid #555; }
        """)

        layout = QVBoxLayout(self)

        # Form
        form_group = QFrame()
        form_group.setStyleSheet("background-color: #252535; border-radius: 5px; padding: 10px;")
        form_layout = QHBoxLayout(form_group)
        self.inp_service = QLineEdit(); self.inp_service.setPlaceholderText("Service")
        self.inp_ports = QLineEdit(); self.inp_ports.setPlaceholderText("Ports")
        self.inp_name = QLineEdit(); self.inp_name.setPlaceholderText("Attack Name")
        self.chk_auth = QCheckBox("Auth Req"); self.chk_danger = QCheckBox("Dangerous")
        btn_add = QPushButton("Add"); btn_add.clicked.connect(self.add_entry)
        
        for w in [self.inp_service, self.inp_ports, self.inp_name, self.chk_auth, self.chk_danger, btn_add]:
            form_layout.addWidget(w)
        layout.addWidget(form_group)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Service", "Ports", "Attack Name", "Auth?", "Dangerous?"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_del = QPushButton("Delete Selected"); btn_del.clicked.connect(self.delete_entry)
        layout.addWidget(btn_del)
        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        vectors = attack_vectors_db.get_all_vectors(self.db_path)
        for i, v in enumerate(vectors):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(v['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(v['service']))
            self.table.setItem(i, 2, QTableWidgetItem(v['ports']))
            self.table.setItem(i, 3, QTableWidgetItem(v['attack_name']))
            self.table.setItem(i, 4, QTableWidgetItem("Yes" if v['auth_required'] else "No"))
            self.table.setItem(i, 5, QTableWidgetItem("Yes" if v['dangerous'] else "No"))

    def add_entry(self):
        if attack_vectors_db.add_attack_vector(self.db_path, self.inp_service.text(), self.inp_ports.text(), 
                                               self.inp_name.text(), self.chk_auth.isChecked(), self.chk_danger.isChecked()):
            self.load_data()

    def delete_entry(self):
        if self.table.currentRow() >= 0:
            vid = self.table.item(self.table.currentRow(), 0).text()
            if QMessageBox.question(self, "Confirm", "Delete vector?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                attack_vectors_db.delete_attack_vector(self.db_path, vid)
                self.load_data()

# ---------------------------------------------------------
# UPDATED: DETAILS DIALOG (3-Dropdown Filter)
# ---------------------------------------------------------
from PyQt5.QtWidgets import QScrollArea, QComboBox, QSizePolicy

class NodeDetailsDialog(QDialog):
    def __init__(self, node_data, db_manager, parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self.db_manager = db_manager
        
        self.setWindowTitle(f"Target Intelligence: {node_data['ip']}")
        self.resize(1100, 750) 
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QLabel { color: #e0e0e0; font-size: 13px; }
            QFrame#Panel { background-color: #252535; border-radius: 10px; }
            QComboBox { 
                background-color: #222; color: #00d2ff; 
                border: 1px solid #4a4a5e; border-radius: 5px; padding: 4px; 
                min-width: 120px;
            }
            QComboBox::drop-down { border: none; }
            QPushButton {
                background-color: #00d2ff; color: #1e1e2f; font-weight: bold;
                border-radius: 5px; padding: 6px 15px;
            }
            QPushButton:hover { background-color: #33eaff; }
            QScrollArea { border: none; background-color: transparent; }
            QWidget#ScrollContent { background-color: transparent; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # --- TOP FILTER BAR ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #2f2f40; border-radius: 8px;")
        filter_frame.setFixedHeight(60)
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(15, 5, 15, 5)
        filter_layout.setSpacing(15)
        
        # 1. Service Dropdown (Dynamic)
        lbl_svc = QLabel("Service:"); lbl_svc.setStyleSheet("font-weight:bold;")
        self.combo_service = QComboBox()
        self.combo_service.addItem("All Services")
        # Logic to populate this is at the end of __init__
        
        # 2. Auth Dropdown
        lbl_auth = QLabel("Auth:"); lbl_auth.setStyleSheet("font-weight:bold;")
        self.combo_auth = QComboBox()
        self.combo_auth.addItems(["All", "Auth Required", "No Auth Required"])
        
        # 3. Risk Dropdown
        lbl_risk = QLabel("Risk:"); lbl_risk.setStyleSheet("font-weight:bold;")
        self.combo_danger = QComboBox()
        self.combo_danger.addItems(["All", "Dangerous Only", "Safe/Info"])
        
        # 4. Apply Button
        btn_apply = QPushButton("Apply Filters")
        btn_apply.setStyleSheet('color: #1e1e2f; background-color: #00d2ff; font-weight: bold;')
        btn_apply.clicked.connect(self.populate_vectors)
        
        # Add widgets to layout
        filter_layout.addWidget(lbl_svc)
        filter_layout.addWidget(self.combo_service)
        filter_layout.addWidget(lbl_auth)
        filter_layout.addWidget(self.combo_auth)
        filter_layout.addWidget(lbl_risk)
        filter_layout.addWidget(self.combo_danger)
        filter_layout.addStretch() # Push everything left
        filter_layout.addWidget(btn_apply)
        
        main_layout.addWidget(filter_frame)
        
        # --- SPLIT CONTENT ---
        splitter = QSplitter(Qt.Horizontal)
        
        # LEFT: Host Information
        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)
        
        # IP Header
        lbl_ip = QLabel(node_data['ip'])
        lbl_ip.setStyleSheet("font-size: 32px; font-weight: bold; color: #00d2ff;")
        left_layout.addWidget(lbl_ip)
        
        # Status
        status_color = "#00ff00" if node_data['live'] else "#ff4444"
        lbl_status = QLabel(f"Status: <span style='color:{status_color};'>{'ONLINE' if node_data['live'] else 'OFFLINE'}</span>")
        lbl_status.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(lbl_status)
        
        left_layout.addWidget(QLabel("_________________________"))
        
        # Port List (Styled)
        lbl_ports = QLabel("Open Ports & Services")
        lbl_ports.setStyleSheet("font-size: 20px; font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(lbl_ports)
        
        self.ports_list = QTreeWidget()
        self.ports_list.setHeaderLabels(["Port", "Service"])
        self.ports_list.setStyleSheet("""
            QTreeWidget { 
                background-color: #1e1e2f; border: 1px solid #4a4a5e; 
                font-size: 14px; color: #fff; border-radius: 5px;
            }
            QHeaderView::section { background-color: #2f2f40; color: white; padding: 5px; font-weight: bold; }
        """)
        left_layout.addWidget(self.ports_list)
        
        splitter.addWidget(left_panel)

        # RIGHT: Attack Vectors (Scrollable Cards)
        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        right_layout = QVBoxLayout(right_panel)
        
        lbl_vec = QLabel("Potential Attack Vectors")
        lbl_vec.setStyleSheet("font-size: 22px; font-weight: bold; color: #ff9999; margin-bottom: 10px;")
        right_layout.addWidget(lbl_vec)
        
        # Scroll Area for Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.cards_layout.setSpacing(10)
        
        scroll.setWidget(self.scroll_content)
        right_layout.addWidget(scroll)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 750]) 
        
        main_layout.addWidget(splitter, 1) 
        
        # Initial Population
        self.populate_host_info()
        self.populate_vectors()

    def populate_host_info(self):
        self.ports_list.clear()
        found_services = set()
        
        for port in self.node_data['ports']:
            svc, _ = self.db_manager.get_attack_info(port)
            item = QTreeWidgetItem(self.ports_list)
            item.setText(0, port)
            item.setText(1, svc)
            found_services.add(svc)
            
        # Dynamically fill the Service Dropdown based on what we found
        for s in sorted(list(found_services)):
            self.combo_service.addItem(s)

    def populate_vectors(self):
        # 1. Clear existing cards
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        found_any = False
        
        # 2. Get Filter States
        target_svc = self.combo_service.currentText()
        target_auth = self.combo_auth.currentText()
        target_risk = self.combo_danger.currentText()

        # 3. Loop through ports and vectors
        for port in self.node_data['ports']:
            svc, vectors = self.db_manager.get_attack_info(port)
            
            # Filter 1: Service Level (Pre-check)
            if target_svc != "All Services" and svc != target_svc:
                continue

            for v in vectors:
                # Filter 2: Auth
                if target_auth == "Auth Required" and not v['auth']: continue
                if target_auth == "No Auth Required" and v['auth']: continue
                
                # Filter 3: Risk
                if target_risk == "Dangerous Only" and not v['dangerous']: continue
                if target_risk == "Safe/Info" and v['dangerous']: continue
                
                # Create Card
                card = AttackVectorCard(v, port)
                self.cards_layout.addWidget(card)
                found_any = True
        
        # 4. Empty State Message
        if not found_any:
            lbl_empty = QLabel(f"No vectors match the current filters.")
            lbl_empty.setStyleSheet("color: #666; font-size: 16px; font-style: italic; margin-top: 20px;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.cards_layout.addWidget(lbl_empty)

# ---------------------------------------------------------
# 3. DATA MANAGER
# ---------------------------------------------------------

class AttackDataManager:
    def __init__(self, project_folder, attack_db_path):
        self.project_folder = project_folder
        self.network_db_path = os.path.join(project_folder, "network_information.db")
        self.attack_db_path = attack_db_path
        
        # Ensure Attack DB exists using utils
        attack_vectors_db.initialize_attack_db(self.attack_db_path)

    def network_db_exists(self):
        return os.path.exists(self.network_db_path)

    def create_network_db(self):
        """Reads naabu_out and scope.txt to create network_information.db."""
        host_port_file = os.path.join(self.project_folder, "naabu_out")
        host_file = os.path.join(self.project_folder, "scope.txt")

        if not os.path.exists(host_port_file) or not os.path.exists(host_file):
            return False, "Missing naabu_out or scope.txt"

        host_ports = defaultdict(set)
        hosts = set()

        # Parse Naabu
        try:
            with open(host_port_file, "r") as f:
                for line in f:
                    if ":" in line:
                        h, p = line.strip().split(":", 1)
                        host_ports[h].add(p)
        except Exception as e: return False, str(e)

        # Parse Scope
        try:
            with open(host_file, "r") as f:
                for line in f:
                    if line.strip(): hosts.add(line.strip())
        except Exception as e: return False, str(e)

        all_hosts = hosts.union(host_ports.keys())
        
        # Create DB
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
            return True, "Success"
        except Exception as e: return False, str(e)

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
# 4. MAIN WIDGET
# ---------------------------------------------------------

class AttackVectorsWidget(QWidget):
    def __init__(self, project_folder, attack_db_path, parent=None):
        super().__init__(parent)
        self.db_manager = AttackDataManager(project_folder, attack_db_path)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # PAGE 1: Create DB Prompt
        self.page_create = QWidget()
        self.setup_create_page()
        self.stack.addWidget(self.page_create)
        
        # PAGE 2: Navigable Map
        self.page_map = QWidget()
        self.setup_map_page()
        self.stack.addWidget(self.page_map)
        
        self.check_database_state()

    def setup_create_page(self):
        layout = QVBoxLayout(self.page_create)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)
        
        layout.addWidget(QLabel("<h2>Network Database Not Found</h2>"))
        
        self.lbl_status = QLabel("Checking file requirements...")
        self.lbl_status.setStyleSheet("color: #aaa;")
        
        self.btn_create = QPushButton("Create Database from Scan Output")
        self.btn_create.setFixedSize(300, 50)
        self.btn_create.setStyleSheet("""
            QPushButton { background-color: #00d2ff; color: #1e1e2f; font-weight: bold; }
            QPushButton:disabled { background-color: #333; color: #555; }
        """)
        self.btn_create.clicked.connect(self.create_db)
        
        btn_check = QPushButton("Re-check Files")
        btn_check.setFixedWidth(200)
        btn_check.clicked.connect(self.check_files_availability)
        
        layout.addWidget(self.lbl_status, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_create, alignment=Qt.AlignCenter)
        layout.addWidget(btn_check, alignment=Qt.AlignCenter)

    def setup_map_page(self):
        layout = QVBoxLayout(self.page_map)
        
        # Toolbar
        bar = QHBoxLayout()
        bar.setContentsMargins(10, 5, 10, 5)
        
        lbl = QLabel("<b>Use Ctrl+Scroll to Zoom, Drag to Pan.</b> Drag nodes to reorganize.")
        lbl.setStyleSheet("color: #888;")
        
        btn_db = QPushButton("⚙ Vectors DB"); btn_db.clicked.connect(self.open_db_mgr)
        btn_ref = QPushButton("↻ Refresh"); btn_ref.clicked.connect(self.refresh_map_view)
        
        btn_reset = QPushButton("✖ Reset DB")
        btn_reset.setStyleSheet("color: #ff4444; border: 1px solid #550000;")
        btn_reset.clicked.connect(self.reset_network_db)
        
        bar.addWidget(lbl)
        bar.addStretch()
        bar.addWidget(btn_reset)
        bar.addWidget(btn_db)
        bar.addWidget(btn_ref)
        layout.addLayout(bar)
        
        # View
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene)
        layout.addWidget(self.view)

    # --- Logic ---

    def check_database_state(self):
        if self.db_manager.network_db_exists():
            self.stack.setCurrentWidget(self.page_map)
            self.refresh_map_view()
        else:
            self.stack.setCurrentWidget(self.page_create)
            self.check_files_availability()

    def check_files_availability(self):
        p_folder = self.db_manager.project_folder
        f1 = os.path.exists(os.path.join(p_folder, "scope.txt"))
        f2 = os.path.exists(os.path.join(p_folder, "naabu_out"))
        
        if f1 and f2:
            self.btn_create.setEnabled(True)
            self.lbl_status.setText("Files found: <span style='color:#0f0'>scope.txt, naabu_out</span>")
        else:
            self.btn_create.setEnabled(False)
            self.lbl_status.setText("Missing: <span style='color:#f44'>scope.txt or naabu_out</span>")

    def create_db(self):
        ok, msg = self.db_manager.create_network_db()
        if ok:
            QMessageBox.information(self, "Success", "Database Created.")
            self.check_database_state()
        else:
            QMessageBox.critical(self, "Error", msg)

    def reset_network_db(self):
        if QMessageBox.question(self, "Reset", "Delete current map?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            try:
                os.remove(self.db_manager.network_db_path)
                self.check_database_state()
            except: pass

    def get_subnet(self, ip):
        parts = ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}" if len(parts) >= 3 else "Unknown"

    def refresh_map_view(self):
        self.scene.clear()
        nodes = self.db_manager.get_all_hosts()
        if not nodes: return

        # Group by subnet
        subnets = defaultdict(list)
        for n in nodes: subnets[self.get_subnet(n['ip'])].append(n)

        hub_x = 0
        spacing = 450
        
        for sn, hosts in subnets.items():
            # Create Hub
            hub = SubnetHubItem(f"{sn}.x")
            hub.setPos(hub_x, 0)
            self.scene.addItem(hub)
            
            # Place Hosts
            count = len(hosts)
            radius = 120 + (count * 5)
            for i, h_data in enumerate(hosts):
                angle = (2 * math.pi * i) / count if count else 0
                nx = hub_x + radius * math.cos(angle)
                ny = radius * math.sin(angle)
                
                node = NetworkNodeItem(h_data, self.open_details)
                node.setPos(nx, ny)
                self.scene.addItem(node)
                self.scene.addItem(ConnectionEdge(hub, node))
            
            hub_x += spacing + radius

        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def open_details(self, data):
        NodeDetailsDialog(data, self.db_manager, self).exec_()

    def open_db_mgr(self):
        DatabaseManagerDialog(self.db_manager.attack_db_path, self).exec_()