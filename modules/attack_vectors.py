import sys
import os
import sqlite3
import math
import re
from collections import defaultdict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QDialog, QHBoxLayout, QLabel, 
                             QTreeWidget, QTreeWidgetItem, QSplitter, QFrame,
                             QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QCheckBox, QStackedWidget, 
                             QGraphicsLineItem, QScrollArea, QComboBox, QSizePolicy,
                             QTabWidget, QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, QPolygonF, QGuiApplication

# Import utilities
from utils import attack_vectors_db, project_db
from utils.enum_db_manager import EnumDBManager


# ---------------------------------------------------------
# 1. CUSTOM GRAPHICS COMPONENTS
# ---------------------------------------------------------

class ZoomableGraphicsView(QGraphicsView):
    """A GraphicsView that supports wheel zooming and panning."""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        
        # CHANGED: Radial Gradient Background to make nodes pop
        self.setStyleSheet("""
            QGraphicsView {
                background: qradialgradient(
                    cx: 0.5, cy: 0.5, radius: 1.0,
                    fx: 0.5, fy: 0.5,
                    stop: 0 #2a2a3a, 
                    stop: 1 #101015
                );
                border: none;
            }
        """)
        
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
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
# 2. UI CARDS (Attack Vector & Enum Command)
# ---------------------------------------------------------

class AttackVectorCard(QFrame):
    def __init__(self, vector_data, port):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            AttackVectorCard { background-color: #2a2a3b; border: 1px solid #3e3e50; border-radius: 8px; margin-bottom: 8px; }
            QLabel#Title { font-size: 16px; font-weight: bold; color: #00d2ff; }
            QLabel#Service { font-size: 12px; font-weight: bold; color: #aaa; }
            QLabel#TagDanger { background-color: #550000; color: #ffcccc; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagSafe { background-color: #224422; color: #ccffcc; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagAuth { background-color: #554400; color: #ffddaa; border-radius: 4px; padding: 4px; font-size: 11px; }
            QLabel#TagNoAuth { background-color: #004444; color: #ccffff; border-radius: 4px; padding: 4px; font-size: 11px; }
        """)
        layout = QVBoxLayout(self)
        lbl_service = QLabel(f"{vector_data['service'].upper()} (Port {port})")
        lbl_service.setObjectName("Service")
        layout.addWidget(lbl_service)
        lbl_title = QLabel(vector_data['name'])
        lbl_title.setObjectName("Title")
        lbl_title.setWordWrap(True)
        layout.addWidget(lbl_title)
        tag_layout = QHBoxLayout()
        tag_layout.setSpacing(10)
        
        if vector_data['dangerous']:
            tag_layout.addWidget(QLabel("DANGEROUS", objectName="TagDanger"))
        else:
            tag_layout.addWidget(QLabel("Safe Check", objectName="TagSafe"))

        if vector_data['auth']:
            tag_layout.addWidget(QLabel("AUTH REQ", objectName="TagAuth"))
        else:
            tag_layout.addWidget(QLabel("NO AUTH", objectName="TagNoAuth"))
            
        tag_layout.addStretch()
        layout.addLayout(tag_layout)

class EnumCommandCard(QFrame):
    """
    Groups multiple commands with the same title into one card.
    Displays commands in a single text box with a large COPY button.
    """
    def __init__(self, title, command_list, target_ip):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            EnumCommandCard { 
                background-color: #252530; 
                border: 1px solid #4a4a5e; 
                border-radius: 6px; 
                margin-bottom: 5px; 
            }
            QLabel#CmdTitle { font-size: 14px; font-weight: bold; color: #e0e0e0; }
            QTextEdit { 
                background-color: #15151b; 
                border: 1px solid #333; 
                color: #00ff00; 
                font-family: Consolas; 
                font-size: 12px; 
            }
            QPushButton { 
                background-color: #3e3e50; 
                color: white; 
                border: none; 
                border-left: 1px solid #4a4a5e;
                border-radius: 0px; 
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                font-weight: bold; 
                font-size: 13px;
            }
            QPushButton:hover { background-color: #00d2ff; color: #1e1e2f; }
        """)
        
        self.lines = []
        is_auth = False
        for cmd in command_list:
            if cmd.get('auth'): is_auth = True
            filled = cmd['command'].replace("{IP}", target_ip)
            self.lines.append(filled)
            
        self.full_text = "\n".join(self.lines)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        header_layout = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setObjectName("CmdTitle")
        header_layout.addWidget(lbl_title)
        
        if is_auth:
            lbl_auth = QLabel(" [AUTH]")
            lbl_auth.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 10px;")
            header_layout.addWidget(lbl_auth)
        header_layout.addStretch()
        left_layout.addLayout(header_layout)
        
        self.txt_cmd = QTextEdit()
        self.txt_cmd.setText(self.full_text)
        self.txt_cmd.setReadOnly(True)
        line_count = len(self.lines)
        box_height = max(45, line_count * 22 + 10)
        self.txt_cmd.setFixedHeight(box_height)
        
        left_layout.addWidget(self.txt_cmd)
        
        btn_copy = QPushButton("COPY")
        btn_copy.setFixedWidth(80) 
        btn_copy.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setToolTip("Copy all commands")
        btn_copy.clicked.connect(self.copy_to_clipboard)

        main_layout.addWidget(left_container, stretch=1)
        main_layout.addWidget(btn_copy)

    def copy_to_clipboard(self):
        cb = QGuiApplication.clipboard()
        cb.setText(self.full_text)

# ---------------------------------------------------------
# 3. DIALOGS
# ---------------------------------------------------------

class DatabaseManagerDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Attack Vectors Database")
        self.setMinimumSize(850, 600)
        self.db_path = db_path
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QTableWidget { background-color: #2f2f40; gridline-color: #4a4a5e; color: #e0e0e0; }
            QLineEdit { background-color: #222; color: #00d2ff; padding: 5px; border: 1px solid #555; }
            QPushButton { padding: 8px; background-color: #3e3e50; color: white; border: 1px solid #555; }
            QPushButton:hover { background-color: #4e4e60; border-color: #00d2ff; }
        """)

        layout = QVBoxLayout(self)

        form_group = QFrame()
        form_group.setStyleSheet("background-color: #252535; border-radius: 5px; padding: 10px;")
        form_layout = QHBoxLayout(form_group)
        self.inp_service = QLineEdit(); self.inp_service.setPlaceholderText("Service")
        self.inp_ports = QLineEdit(); self.inp_ports.setPlaceholderText("Ports")
        self.inp_name = QLineEdit(); self.inp_name.setPlaceholderText("Attack Name")
        self.chk_auth = QCheckBox("Auth Req"); self.chk_danger = QCheckBox("Dangerous")
        btn_add = QPushButton("Add Vector"); btn_add.clicked.connect(self.add_entry)
        
        form_layout.addWidget(self.inp_service)
        form_layout.addWidget(self.inp_ports)
        form_layout.addWidget(self.inp_name)
        form_layout.addWidget(self.chk_auth)
        form_layout.addWidget(self.chk_danger)
        form_layout.addWidget(btn_add)
        layout.addWidget(form_group)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Service", "Ports", "Attack Name", "Auth?", "Dangerous?"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self.delete_entry)
        
        btn_import = QPushButton("Import CSV...")
        btn_import.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        btn_import.clicked.connect(self.import_csv)
        
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_import)
        
        layout.addLayout(btn_layout)
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
            self.inp_name.clear()

    def delete_entry(self):
        if self.table.currentRow() >= 0:
            vid = self.table.item(self.table.currentRow(), 0).text()
            if QMessageBox.question(self, "Confirm", "Delete vector?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                attack_vectors_db.delete_attack_vector(self.db_path, vid)
                self.load_data()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if path:
            success, msg = attack_vectors_db.import_from_csv(self.db_path, path)
            if success:
                QMessageBox.information(self, "Import Successful", msg)
                self.load_data()
            else:
                QMessageBox.critical(self, "Import Failed", msg)

# ---------------------------------------------------------
# 4. NODE DETAILS DIALOG (The Cross-Compare Logic)
# ---------------------------------------------------------

class NodeDetailsDialog(QDialog):
    def __init__(self, node_data, db_manager, parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self.db_manager = db_manager
        self.enum_db = EnumDBManager() 
        
        self.setWindowTitle(f"Target Intelligence: {node_data['ip']}")
        self.resize(1200, 800) 
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2f; color: white; }
            QLabel { color: #e0e0e0; font-size: 13px; }
            QFrame#Panel { background-color: #252535; border-radius: 10px; }
            QComboBox { background-color: #222; color: #00d2ff; border: 1px solid #4a4a5e; border-radius: 5px; padding: 4px; min-width: 120px; }
            QPushButton { background-color: #00d2ff; color: #1e1e2f; font-weight: bold; border-radius: 5px; padding: 6px 15px; }
            QPushButton:hover { background-color: #33eaff; }
            QTabWidget::pane { border: 1px solid #4a4a5e; background-color: #252535; }
            QTabBar::tab { background: #2f2f40; color: #aaa; padding: 10px 20px; margin-right: 2px; }
            QTabBar::tab:selected { background: #00d2ff; color: #1e1e2f; font-weight: bold; }
            QScrollArea { border: none; background-color: transparent; }
            QWidget#ScrollContent { background-color: transparent; }
        """)
        
        main_layout = QVBoxLayout(self)
        
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #2f2f40; border-radius: 8px;")
        filter_frame.setFixedHeight(60)
        filter_layout = QHBoxLayout(filter_frame)
        
        self.combo_service = QComboBox(); self.combo_service.addItem("All Services")
        self.combo_auth = QComboBox(); self.combo_auth.addItems(["All", "Auth Required", "No Auth Required"])
        self.combo_danger = QComboBox(); self.combo_danger.addItems(["All", "Dangerous Only", "Safe/Info"])
        btn_apply = QPushButton("Apply Filters")
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #00d2ff;
                color: #1e1e2f;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #33eaff;
            }
        """); btn_apply.clicked.connect(self.refresh_views)
        
        filter_layout.addWidget(QLabel("Service:"))
        filter_layout.addWidget(self.combo_service)
        filter_layout.addWidget(QLabel("Auth:"))
        filter_layout.addWidget(self.combo_auth)
        filter_layout.addWidget(QLabel("Risk:"))
        filter_layout.addWidget(self.combo_danger)
        filter_layout.addStretch()
        filter_layout.addWidget(btn_apply)
        main_layout.addWidget(filter_frame)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QFrame(); left_panel.setObjectName("Panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel(node_data['ip'], styleSheet="font-size: 32px; font-weight: bold; color: #00d2ff;"))
        status_color = "#00ff00" if node_data['live'] else "#ff4444"
        left_layout.addWidget(QLabel(f"Status: <span style='color:{status_color};'>{'ONLINE' if node_data['live'] else 'OFFLINE'}</span>", styleSheet="font-size: 18px;"))
        left_layout.addWidget(QLabel("_________________________"))
        
        self.ports_list = QTreeWidget()
        self.ports_list.setHeaderLabels(["Port", "Service"])
        self.ports_list.setStyleSheet("background-color: #1e1e2f; border: 1px solid #4a4a5e; color: #fff;")
        left_layout.addWidget(self.ports_list)
        splitter.addWidget(left_panel)

        self.tabs = QTabWidget()
        
        self.tab_vectors = QWidget()
        vec_layout = QVBoxLayout(self.tab_vectors)
        vec_layout.addWidget(QLabel("Potential Attack Vectors", styleSheet="font-size: 18px; font-weight: bold; color: #ff9999;"))
        
        scroll_vec = QScrollArea(); scroll_vec.setWidgetResizable(True)
        self.scroll_vec_content = QWidget(); self.scroll_vec_content.setObjectName("ScrollContent")
        self.vec_layout = QVBoxLayout(self.scroll_vec_content); self.vec_layout.setAlignment(Qt.AlignTop)
        scroll_vec.setWidget(self.scroll_vec_content)
        vec_layout.addWidget(scroll_vec)
        
        self.tabs.addTab(self.tab_vectors, "Attack Vectors")

        self.tab_enum = QWidget()
        enum_layout = QVBoxLayout(self.tab_enum)
        enum_layout.addWidget(QLabel("Enumeration Commands (Ready to Run)", styleSheet="font-size: 18px; font-weight: bold; color: #00d2ff;"))
        
        scroll_enum = QScrollArea(); scroll_enum.setWidgetResizable(True)
        self.scroll_enum_content = QWidget(); self.scroll_enum_content.setObjectName("ScrollContent")
        self.enum_layout = QVBoxLayout(self.scroll_enum_content); self.enum_layout.setAlignment(Qt.AlignTop)
        scroll_enum.setWidget(self.scroll_enum_content)
        enum_layout.addWidget(scroll_enum)
        
        self.tabs.addTab(self.tab_enum, "Enumeration Guide")
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([350, 850])
        main_layout.addWidget(splitter)
        
        self.populate_host_info()
        self.refresh_views()

    def populate_host_info(self):
        self.ports_list.clear()
        # Add a third column for Version
        self.ports_list.setColumnCount(3)
        self.ports_list.setHeaderLabels(["Port", "Service", "Version"])
        
        found_services = set()
        self.host_services = {} 
        
        # 'versions' is now a dict created in get_all_hosts: {"80": "SimpleHTTPServer 0.6"}
        ver_map = self.node_data.get('versions', {})
        
        for port in self.node_data['ports']:
            svc, _ = self.db_manager.get_attack_info(port)
            self.host_services[port] = svc
            
            item = QTreeWidgetItem(self.ports_list)
            item.setText(0, port)
            item.setText(1, svc)
            item.setText(2, ver_map.get(port, "n/a"))
            
            found_services.add(svc)
            
        for s in sorted(list(found_services)): 
            self.combo_service.addItem(s)

    def refresh_views(self):
        self.populate_vectors()
        self.populate_enumeration()

    def populate_vectors(self):
        while self.vec_layout.count():
            child = self.vec_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        target_svc = self.combo_service.currentText()
        target_auth = self.combo_auth.currentText()
        target_risk = self.combo_danger.currentText()
        found_any = False

        for port in self.node_data['ports']:
            svc, vectors = self.db_manager.get_attack_info(port)
            if target_svc != "All Services" and svc != target_svc: continue

            for v in vectors:
                if target_auth == "Auth Required" and not v['auth']: continue
                if target_auth == "No Auth Required" and v['auth']: continue
                if target_risk == "Dangerous Only" and not v['dangerous']: continue
                if target_risk == "Safe/Info" and v['dangerous']: continue
                
                self.vec_layout.addWidget(AttackVectorCard(v, port))
                found_any = True
        
        if not found_any:
            self.vec_layout.addWidget(QLabel("No vectors match filters.", alignment=Qt.AlignCenter, styleSheet="color: #666; font-size: 16px;"))

    def populate_enumeration(self):
        while self.enum_layout.count():
            child = self.enum_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        target_svc = self.combo_service.currentText()
        found_cmds = False
        
        services_to_query = set()
        for port, svc in self.host_services.items():
            if target_svc == "All Services" or svc == target_svc:
                services_to_query.add(svc)
        
        for svc in services_to_query:
            commands = self.enum_db.get_commands(svc)
            if commands:
                header = QLabel(f"Service: {svc.upper()}")
                header.setStyleSheet("color: #aaa; font-weight: bold; margin-top: 15px; border-bottom: 1px solid #444;")
                self.enum_layout.addWidget(header)
                
                grouped_cmds = defaultdict(list)
                for c in commands:
                    grouped_cmds[c['title']].append(c)

                for title, cmd_list in grouped_cmds.items():
                    card = EnumCommandCard(title, cmd_list, self.node_data['ip'])
                    self.enum_layout.addWidget(card)
                    found_cmds = True
                    
        if not found_cmds:
             self.enum_layout.addWidget(QLabel("No enumeration commands found for these services.", alignment=Qt.AlignCenter, styleSheet="color: #666; font-size: 16px;"))


# ---------------------------------------------------------
# 5. DATA MANAGER
# ---------------------------------------------------------

class AttackDataManager:
    def __init__(self, project_folder, attack_db_path=None):
        self.project_folder = project_folder
        self.network_db_path = os.path.join(project_folder, "network_information.db")
        self.project_db_path = os.path.join(project_folder, "project_data.db") # Path to main project DB
        self.attack_db_path = attack_vectors_db.initialize_attack_db(attack_db_path)

    def network_db_exists(self):
        return os.path.exists(self.network_db_path)

    def create_network_db(self):
        nmap_file = os.path.join(self.project_folder, "nmap_out")
        
        if not os.path.exists(nmap_file):
            return False, "Missing nmap_out file."

        # Temporary storage: { "IP": {"ports": [], "versions": []} }
        host_data = defaultdict(lambda: {"ports": [], "versions": []})

        try:
            current_ip = None
            with open(nmap_file, "r") as f:
                for line in f:
                    line = line.strip()
                    
                    # 1. Capture IP from Nmap report line
                    ip_match = re.search(r"Nmap scan report for (?:.*\((\d+\.\d+\.\d+\.\d+)\)|(\d+\.\d+\.\d+\.\d+))", line)
                    if ip_match:
                        current_ip = ip_match.group(1) if ip_match.group(1) else ip_match.group(2)
                        continue

                    # 2. Capture Numeric Port (Group 1) and Version String (Group 3)
                    # Regex matches: [Port]/[Proto] [State] [Service] [Version...]
                    port_match = re.match(r"^(\d+)/(?:tcp|udp)\s+open\s+[^\s]+\s+(.*)$", line)
                    if current_ip and port_match:
                        p_num = port_match.group(1)
                        v_info = port_match.group(2).strip() or "n/a"
                        
                        host_data[current_ip]["ports"].append(p_num)
                        host_data[current_ip]["versions"].append(v_info)

        except Exception as e:
            return False, f"Parse Error: {str(e)}"

        # Save to SQLite using your specified structure
        try:
            conn = sqlite3.connect(self.network_db_path)
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS hosts")
            cur.execute("CREATE TABLE hosts (host TEXT PRIMARY KEY, ports TEXT, versions TEXT, live BOOLEAN)")
            
            for ip, info in host_data.items():
                ports_str = ",".join(info["ports"])
                versions_str = "|".join(info["versions"]) # Using pipe to avoid conflict with commas in version names
                cur.execute("INSERT OR REPLACE INTO hosts VALUES (?, ?, ?, ?)", (ip, ports_str, versions_str, True))
            
            conn.commit()
            conn.close()

        except Exception as e:
            return False, str(e)

        # 2. Populate 'enum' table in project_data.db
        # We need to resolve port -> service using attack_vectors_db
        enum_data = []
        for host, info in host_data.items():
            for port in info["ports"]:
                # Cross-compare with attack_vectors.db to get Service Name
                # Note: port is already a numeric string here
                service_name, _ = attack_vectors_db.get_vectors_for_port(self.attack_db_path, port)
                
                if service_name != "unknown":
                    enum_data.append({
                        'host': host,
                        'port': port,
                        'service': service_name
                    })
        
        # Sync to Project DB
        if os.path.exists(self.project_db_path):
            project_db.sync_enum_data(self.project_db_path, enum_data)

        return True, "Success"

    def get_all_hosts(self):
        nodes = []
        if not self.network_db_exists(): return nodes
        try:
            conn = sqlite3.connect(self.network_db_path)
            c = conn.cursor()
            c.execute("SELECT host, ports, versions, live FROM hosts")
            for r in c.fetchall():
                ports = [p for p in r[1].split(',') if p]
                # Reconstruct list from pipe-separated string
                versions_list = r[2].split('|') if r[2] else []
                
                # Build a dictionary for the UI to map port -> version
                ver_map = dict(zip(ports, versions_list))
                
                nodes.append({
                    "ip": r[0], 
                    "ports": ports, 
                    "versions": ver_map, 
                    "live": bool(r[3]),
                    "type": "Server" if len(ports) > 3 else "Client"
                })
            conn.close()
        except: pass
        return nodes

    def get_attack_info(self, port):
        return attack_vectors_db.get_vectors_for_port(self.attack_db_path, port)

# ---------------------------------------------------------
# 6. MAIN WIDGET
# ---------------------------------------------------------

class AttackVectorsWidget(QWidget):
    def __init__(self, project_folder, attack_db_path=None, parent=None):
        super().__init__(parent)
        self.db_manager = AttackDataManager(project_folder, attack_db_path)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self.page_create = QWidget()
        self.setup_create_page()
        self.stack.addWidget(self.page_create)
        
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
        self.btn_create.setStyleSheet("background-color: #00d2ff; color: #1e1e2f; font-weight: bold;")
        self.btn_create.clicked.connect(self.create_db)
        btn_check = QPushButton("Re-check Files")
        btn_check.setFixedWidth(200)
        btn_check.clicked.connect(self.check_files_availability)
        layout.addWidget(self.lbl_status, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_create, alignment=Qt.AlignCenter)
        layout.addWidget(btn_check, alignment=Qt.AlignCenter)

    def setup_map_page(self):
        layout = QVBoxLayout(self.page_map)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>Use Ctrl+Scroll to Zoom, Drag to Pan.</b> Drag nodes to reorganize.", styleSheet="color: #888;"))
        bar.addStretch()
        btn_reset = QPushButton("✖ Reset DB"); btn_reset.setStyleSheet("color: #ff4444; border: 1px solid #550000;")
        btn_reset.clicked.connect(self.reset_network_db)
        btn_db = QPushButton("⚙ Vectors DB"); btn_db.clicked.connect(self.open_db_mgr)
        btn_ref = QPushButton("↻ Refresh"); btn_ref.clicked.connect(self.refresh_map_view)
        bar.addWidget(btn_reset); bar.addWidget(btn_db); bar.addWidget(btn_ref)
        layout.addLayout(bar)
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene)
        layout.addWidget(self.view)

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
        f2 = os.path.exists(os.path.join(p_folder, "nmap_out"))
        if f1 and f2:
            self.btn_create.setEnabled(True)
            self.lbl_status.setText("Files found: <span style='color:#0f0'>scope.txt, nmap_out</span>")
        elif f1 or f2:
            missing = "nmap_out" if f1 else "scope.txt"
            self.btn_create.setEnabled(False)
            self.lbl_status.setText(f"Missing: <span style='color:#f44'>{missing}</span>")
        else:
            self.btn_create.setEnabled(False)
            self.lbl_status.setText("Missing: <span style='color:#f44'>scope.txt or nmap_out</span>")

    def create_db(self):
        ok, msg = self.db_manager.create_network_db()
        if ok:
            QMessageBox.information(self, "Success", "Database Created.")
            self.check_database_state()
        else:
            QMessageBox.critical(self, "Error", msg)

    def reset_network_db(self):
        if QMessageBox.question(self, "Reset", "Delete current map?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            try: os.remove(self.db_manager.network_db_path); self.check_database_state()
            except: pass

    def get_subnet(self, ip):
        parts = ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}" if len(parts) >= 3 else "Unknown"

    def refresh_map_view(self):
        self.scene.clear()
        nodes = self.db_manager.get_all_hosts()
        if not nodes: return
        subnets = defaultdict(list)
        for n in nodes: subnets[self.get_subnet(n['ip'])].append(n)
        hub_x = 0
        for sn, hosts in subnets.items():
            hub = SubnetHubItem(f"{sn}.x")
            hub.setPos(hub_x, 0)
            self.scene.addItem(hub)
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
            hub_x += 450 + radius
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def open_details(self, data):
        NodeDetailsDialog(data, self.db_manager, self).exec_()

    def open_db_mgr(self):
        DatabaseManagerDialog(self.db_manager.attack_db_path, self).exec_()
    
    # ADDED HELPER for refreshing
    def refresh_view(self):
        self.check_database_state()
