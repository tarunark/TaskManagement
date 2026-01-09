import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget,
                             QTableWidgetItem, QTextEdit, QLabel, QPushButton, 
                             QSplitter, QDialog, QLineEdit, QSpinBox, QComboBox,
                             QDateEdit, QCheckBox, QMessageBox, QHeaderView, QMenu,
                             QAction, QDialogButtonBox, QFormLayout, QGroupBox)
from PyQt5.QtCore import Qt, QDate, QMimeData
from PyQt5.QtGui import QColor, QDrag, QFont


class Task:
    def __init__(self, id, title, parent_id=None, description="", priority="Medium",
                 tags=None, created_date=None, completed_date=None, state="active",
                 notes="", references=None):
        self.id = id
        self.title = title
        self.parent_id = parent_id
        self.description = description
        self.priority = priority
        self.tags = tags or []
        self.created_date = created_date or datetime.now().isoformat()
        self.completed_date = completed_date
        self.state = state  # active, completed, archived, dormant
        self.notes = notes
        self.references = references or []
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'parent_id': self.parent_id,
            'description': self.description,
            'priority': self.priority,
            'tags': self.tags,
            'created_date': self.created_date,
            'completed_date': self.completed_date,
            'state': self.state,
            'notes': self.notes,
            'references': self.references
        }
    
    @staticmethod
    def from_dict(data):
        #print(data)
        
        return Task(**data)


class TaskManager:
    def __init__(self, data_file="tasks.json"):
        self.data_file = Path(data_file)
        self.tasks = {}
        self.schedule = {}  # {date: {slot: task_id}}
        self.next_id = 1
        self.load_data()
    
    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.tasks = {t['id']: Task.from_dict(t) for t in data.get('tasks', [])}
                self.schedule = data.get('schedule', {})
                self.next_id = data.get('next_id', 1)
        self.check_old_tasks()
    
    def save_data(self):
        data = {
            'tasks': [t.to_dict() for t in self.tasks.values()],
            'schedule': self.schedule,
            'next_id': self.next_id
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_old_tasks(self):
        """Archive completed tasks older than a week and old tasks older than a year"""
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        one_year_ago = now - timedelta(days=365)
        
        for task in self.tasks.values():
            if task.state == "completed" and task.completed_date:
                completed = datetime.fromisoformat(task.completed_date)
                # Keep completed tasks greyed until end of following week
                days_until_end_of_next_week = (7 - completed.weekday()) + 7
                archive_date = completed + timedelta(days=days_until_end_of_next_week)
                if now > archive_date:
                    task.state = "archived"
            
            created = datetime.fromisoformat(task.created_date)
            if task.state == "archived" and (now - created).days > 365:
                task.state = "dormant"
    
    def create_task(self, title, parent_id=None, **kwargs):
        task = Task(self.next_id, title, parent_id, **kwargs)
        self.tasks[self.next_id] = task
        self.next_id += 1
        self.save_data()
        return task
    
    def update_task(self, task_id, **kwargs):
        if task_id in self.tasks:
            task = self.tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self.save_data()
    
    def delete_task(self, task_id):
        if task_id in self.tasks:
            # Remove children references
            for task in self.tasks.values():
                if task.parent_id == task_id:
                    task.parent_id = None
            del self.tasks[task_id]
            self.save_data()
    
    def mark_completed(self, task_id):
        if task_id in self.tasks:
            self.tasks[task_id].state = "completed"
            self.tasks[task_id].completed_date = datetime.now().isoformat()
            self.save_data()
    
    def get_children(self, parent_id):
        return [t for t in self.tasks.values() if t.parent_id == parent_id]
    
    def get_root_tasks(self):
        return [t for t in self.tasks.values() if t.parent_id is None]
    
    def schedule_task(self, task_id, date, slot):
        date_str = date if isinstance(date, str) else date.toString("yyyy-MM-dd")
        if date_str not in self.schedule:
            self.schedule[date_str] = {}
        self.schedule[date_str][slot] = task_id
        self.save_data()
    
    def unschedule_task(self, date, slot):
        date_str = date if isinstance(date, str) else date.toString("yyyy-MM-dd")
        if date_str in self.schedule and slot in self.schedule[date_str]:
            del self.schedule[date_str][slot]
            self.save_data()
    
    def search_tasks(self, keyword, include_dormant=False):
        results = []
        for task in self.tasks.values():
            if task.state == "dormant" and not include_dormant:
                continue
            if (keyword.lower() in task.title.lower() or 
                keyword.lower() in task.notes.lower() or
                keyword.lower() in task.description.lower()):
                results.append(task)
        return results
    
    def get_tasks_with_notes_in_range(self, start_date, end_date):
        results = []
        start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
        
        for task in self.tasks.values():
            if task.notes and task.state != "dormant":
                # Check if task was created or completed in range
                created = datetime.fromisoformat(task.created_date)
                if start <= created <= end:
                    results.append(task)
                elif task.completed_date:
                    completed = datetime.fromisoformat(task.completed_date)
                    if start <= completed <= end:
                        results.append(task)
        return results


class SettingsDialog(QDialog):
    def __init__(self, parent=None, slots_per_day=7, hours_per_slot=2):
        super().__init__(parent)
        self.setWindowTitle("Week Planning Settings")
        self.slots_per_day = slots_per_day
        self.hours_per_slot = hours_per_slot
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        
        self.slots_spin = QSpinBox()
        self.slots_spin.setRange(2, 6)
        self.slots_spin.setValue(self.slots_per_day)
        layout.addRow("Slots per day:", self.slots_spin)
        
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 4)
        self.hours_spin.setValue(self.hours_per_slot)
        layout.addRow("Hours per slot:", self.hours_spin)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_values(self):
        return self.slots_spin.value(), self.hours_spin.value()


class TaskDialog(QDialog):
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("Edit Task" if task else "New Task")
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        
        self.title_edit = QLineEdit()
        if self.task:
            self.title_edit.setText(self.task.title)
        layout.addRow("Title:", self.title_edit)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(60)
        if self.task:
            self.desc_edit.setPlainText(self.task.description)
        layout.addRow("Description:", self.desc_edit)
        
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High", "Critical"])
        if self.task:
            self.priority_combo.setCurrentText(self.task.priority)
        else:
            self.priority_combo.setCurrentText("Medium")
        layout.addRow("Priority:", self.priority_combo)
        
        self.tags_edit = QLineEdit()
        if self.task:
            self.tags_edit.setText(", ".join(self.task.tags))
        layout.addRow("Tags (comma separated):", self.tags_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_values(self):
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return {
            'title': self.title_edit.text(),
            'description': self.desc_edit.toPlainText(),
            'priority': self.priority_combo.currentText(),
            'tags': tags
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task_manager = TaskManager()
        self.current_task = None
        self.slots_per_day = 7
        self.hours_per_slot = 2
        self.current_week_start = self.get_week_start(QDate.currentDate())
        self.init_ui()
        self.load_tasks()
        self.load_schedule()
    
    def init_ui(self):
        self.setWindowTitle("Task Manager & Weekly Planner")
        self.setGeometry(100, 100, 1400, 800)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Task Tree
        left_panel = self.create_task_tree_panel()
        splitter.addWidget(left_panel)
        
        # Middle panel - Weekly Schedule
        middle_panel = self.create_schedule_panel()
        splitter.addWidget(middle_panel)
        
        # Right panel - Task Details
        right_panel = self.create_details_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 600, 400])
        main_layout.addWidget(splitter)
        
        # Menu bar
        self.create_menu_bar()
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        settings_action = QAction("Week Settings", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Search menu
        search_menu = menubar.addMenu("Search")
        
        search_action = QAction("Search Tasks", self)
        search_action.triggered.connect(self.show_search_dialog)
        search_menu.addAction(search_action)
        
        notes_action = QAction("Tasks with Notes (Last Week)", self)
        notes_action.triggered.connect(self.show_notes_shortlist)
        search_menu.addAction(notes_action)
    
    def create_task_tree_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("Task Tree")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Buttons
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("New Task")
        new_btn.clicked.connect(self.create_new_task)
        btn_layout.addWidget(new_btn)
        
        new_child_btn = QPushButton("New Subtask")
        new_child_btn.clicked.connect(self.create_new_subtask)
        btn_layout.addWidget(new_child_btn)
        
        layout.addLayout(btn_layout)
        
        # Task tree
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["Title", "Priority", "Tags"])
        self.task_tree.setColumnWidth(0, 200)
        self.task_tree.itemClicked.connect(self.on_task_selected)
        self.task_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.show_task_context_menu)
        self.task_tree.setDragEnabled(True)
        self.task_tree.setAcceptDrops(True)
        self.task_tree.setDragDropMode(QTreeWidget.DragDrop)
        self.task_tree.setDefaultDropAction(Qt.CopyAction)
        self.task_tree.startDrag = lambda actions: self.start_tree_drag(actions)
        layout.addWidget(self.task_tree)
        
        return panel
    
    def create_schedule_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Header with navigation
        header_layout = QHBoxLayout()
        header = QLabel("Weekly Schedule")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        prev_btn = QPushButton("← Prev Week")
        prev_btn.clicked.connect(self.prev_week)
        header_layout.addWidget(prev_btn)
        
        self.week_label = QLabel()
        self.update_week_label()
        header_layout.addWidget(self.week_label)
        
        next_btn = QPushButton("Next Week →")
        next_btn.clicked.connect(self.next_week)
        header_layout.addWidget(next_btn)
        
        layout.addLayout(header_layout)
        
        # Schedule table
        self.schedule_table = QTableWidget()
        self.setup_schedule_table()
        self.schedule_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.schedule_table.customContextMenuRequested.connect(self.show_schedule_context_menu)
        self.schedule_table.setAcceptDrops(True)
        self.schedule_table.setDragEnabled(True)
        self.schedule_table.setDragDropMode(QTableWidget.DragDrop)
        self.schedule_table.dragEnterEvent = self.schedule_drag_enter
        self.schedule_table.dragMoveEvent = self.schedule_drag_move
        self.schedule_table.dropEvent = self.schedule_drop
        layout.addWidget(self.schedule_table)
        
        return panel
    
    def create_details_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Header
        header = QLabel("Task Details")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        
        # Task info
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()
        self.task_info_label = QLabel("No task selected")
        self.task_info_label.setWordWrap(True)
        info_layout.addWidget(self.task_info_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Notes
        notes_label = QLabel("Notes:")
        layout.addWidget(notes_label)
        self.notes_edit = QTextEdit()
        self.notes_edit.textChanged.connect(self.on_notes_changed)
        layout.addWidget(self.notes_edit)
        
        # References
        refs_label = QLabel("References:")
        layout.addWidget(refs_label)
        self.refs_edit = QTextEdit()
        self.refs_edit.setMaximumHeight(80)
        self.refs_edit.textChanged.connect(self.on_refs_changed)
        layout.addWidget(self.refs_edit)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_current_task)
        btn_layout.addWidget(edit_btn)
        
        complete_btn = QPushButton("Mark Done")
        complete_btn.clicked.connect(self.mark_task_complete)
        btn_layout.addWidget(complete_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_current_task)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def setup_schedule_table(self):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        self.schedule_table.setRowCount(self.slots_per_day)
        self.schedule_table.setColumnCount(len(days))
        self.schedule_table.setHorizontalHeaderLabels(days)
        

        slots = ['9:00', '10:00', '12:00', '12:30', '14:30', '16:00', '18:00', '19:00'];
        for i in range(0, len(slots)-1):
            start_hour = str(slots[i]) #9 + i * self.hours_per_slot
            end_hour = str(slots[i+1])#start_hour + self.hours_per_slot
            self.schedule_table.setVerticalHeaderItem(i, QTableWidgetItem(start_hour+ '-' + end_hour))
        
        #for i in range(self.slots_per_day):
        #    start_hour = 9 + i * self.hours_per_slot
        #    end_hour = start_hour + self.hours_per_slot
        #    self.schedule_table.setVerticalHeaderItem(i, QTableWidgetItem(f"{start_hour}:00-{end_hour}:00"))
        
        
        self.schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.schedule_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
    
    def get_week_start(self, date):
        days_to_monday = date.dayOfWeek() - 1
        return date.addDays(-days_to_monday)
    
    def update_week_label(self):
        end_date = self.current_week_start.addDays(4)
        self.week_label.setText(f"{self.current_week_start.toString('MMM dd')} - {end_date.toString('MMM dd, yyyy')}")
    
    def prev_week(self):
        self.current_week_start = self.current_week_start.addDays(-7)
        self.update_week_label()
        self.load_schedule()
    
    def next_week(self):
        self.current_week_start = self.current_week_start.addDays(7)
        self.update_week_label()
        self.load_schedule()
    
    def load_tasks(self):
        self.task_tree.clear()
        root_tasks = self.task_manager.get_root_tasks()
        for task in root_tasks:
            if task.state not in ["dormant"]:
                self.add_task_to_tree(task, None)
    
    def add_task_to_tree(self, task, parent_item):
        item = QTreeWidgetItem()
        item.setText(0, task.title)
        item.setText(1, task.priority)
        item.setText(2, ", ".join(task.tags))
        item.setData(0, Qt.UserRole, task.id)
        
        # Style based on state
        if task.state == "completed":
            for i in range(3):
                item.setForeground(i, QColor(150, 150, 150))
            font = item.font(0)
            font.setStrikeOut(True)
            item.setFont(0, font)
        elif task.state == "archived":
            for i in range(3):
                item.setForeground(i, QColor(200, 200, 200))
        
        if parent_item:
            parent_item.addChild(item)
        else:
            self.task_tree.addTopLevelItem(item)
        
        # Add children recursively
        children = self.task_manager.get_children(task.id)
        for child in children:
            if child.state not in ["dormant"]:
                self.add_task_to_tree(child, item)
        
        item.setExpanded(True)
    
    def load_schedule(self):
        # Clear existing items
        for row in range(self.schedule_table.rowCount()):
            for col in range(self.schedule_table.columnCount()):
                self.schedule_table.setItem(row, col, QTableWidgetItem(""))
        
        # Load scheduled tasks
        for day_offset in range(5):
            date = self.current_week_start.addDays(day_offset)
            date_str = date.toString("yyyy-MM-dd")
            
            if date_str in self.task_manager.schedule:
                for slot_str, task_id in self.task_manager.schedule[date_str].items():
                    slot = int(slot_str)
                    if slot < self.schedule_table.rowCount() and task_id in self.task_manager.tasks:
                        task = self.task_manager.tasks[task_id]
                        item = QTableWidgetItem(task.title)
                        item.setData(Qt.UserRole, task_id)
                        self.schedule_table.setItem(slot, day_offset, item)
    
    def on_task_selected(self, item, column):
        task_id = item.data(0, Qt.UserRole)
        if task_id in self.task_manager.tasks:
            self.current_task = self.task_manager.tasks[task_id]
            self.display_task_details()
    
    def display_task_details(self):
        if not self.current_task:
            return
        
        info = f"<b>Title:</b> {self.current_task.title}<br>"
        info += f"<b>Description:</b> {self.current_task.description}<br>"
        info += f"<b>Priority:</b> {self.current_task.priority}<br>"
        info += f"<b>Tags:</b> {', '.join(self.current_task.tags)}<br>"
        info += f"<b>Created:</b> {self.current_task.created_date[:10]}<br>"
        info += f"<b>State:</b> {self.current_task.state}"
        
        self.task_info_label.setText(info)
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(self.current_task.notes)
        self.notes_edit.blockSignals(False)
        
        self.refs_edit.blockSignals(True)
        self.refs_edit.setPlainText("\n".join(self.current_task.references))
        self.refs_edit.blockSignals(False)
    
    def on_notes_changed(self):
        if self.current_task:
            self.task_manager.update_task(self.current_task.id, notes=self.notes_edit.toPlainText())
    
    def on_refs_changed(self):
        if self.current_task:
            refs = [r.strip() for r in self.refs_edit.toPlainText().split("\n") if r.strip()]
            self.task_manager.update_task(self.current_task.id, references=refs)
    
    def create_new_task(self):
        dialog = TaskDialog(self)
        if dialog.exec_():
            values = dialog.get_values()
            self.task_manager.create_task(**values)
            self.load_tasks()
    
    def create_new_subtask(self):
        if not self.current_task:
            QMessageBox.warning(self, "Warning", "Please select a parent task first")
            return
        
        dialog = TaskDialog(self)
        if dialog.exec_():
            values = dialog.get_values()
            values['parent_id'] = self.current_task.id
            self.task_manager.create_task(**values)
            self.load_tasks()
    
    def edit_current_task(self):
        if not self.current_task:
            return
        
        dialog = TaskDialog(self, self.current_task)
        if dialog.exec_():
            values = dialog.get_values()
            self.task_manager.update_task(self.current_task.id, **values)
            self.load_tasks()
            self.display_task_details()
    
    def mark_task_complete(self):
        if not self.current_task:
            return
        
        self.task_manager.mark_completed(self.current_task.id)
        self.load_tasks()
        self.display_task_details()
    
    def delete_current_task(self):
        if not self.current_task:
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                      f"Delete task '{self.current_task.title}'?",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.task_manager.delete_task(self.current_task.id)
            self.current_task = None
            self.load_tasks()
            self.task_info_label.setText("No task selected")
            self.notes_edit.clear()
            self.refs_edit.clear()
    
    def show_task_context_menu(self, position):
        menu = QMenu()
        
        item = self.task_tree.itemAt(position)
        if item:
            edit_action = menu.addAction("Edit")
            complete_action = menu.addAction("Mark Done")
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
            
            action = menu.exec_(self.task_tree.viewport().mapToGlobal(position))
            
            if action == edit_action:
                self.edit_current_task()
            elif action == complete_action:
                self.mark_task_complete()
            elif action == delete_action:
                self.delete_current_task()
    
    def show_schedule_context_menu(self, position):
        menu = QMenu()
        clear_action = menu.addAction("Clear Slot")
        
        action = menu.exec_(self.schedule_table.viewport().mapToGlobal(position))
        
        if action == clear_action:
            item = self.schedule_table.itemAt(position)
            if item:
                row = self.schedule_table.row(item)
                col = self.schedule_table.column(item)
                date = self.current_week_start.addDays(col)
                self.task_manager.unschedule_task(date.toString("yyyy-MM-dd"), str(row))
                self.load_schedule()
    
    def start_tree_drag(self, supported_actions):
        """Custom drag handler to prevent item removal from tree"""
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        task_id = item.data(0, Qt.UserRole)
        
        drag = QDrag(self.task_tree)
        mime_data = QMimeData()
        mime_data.setText(str(task_id))
        drag.setMimeData(mime_data)
        
        # Use CopyAction to prevent removal from tree
        drag.exec_(Qt.CopyAction)
    
    def schedule_drag_enter(self, event):
        event.accept()
    
    def schedule_drag_move(self, event):
        event.accept()
    
    def schedule_drop(self, event):
        position = event.pos()
        row = self.schedule_table.rowAt(position.y())
        col = self.schedule_table.columnAt(position.x())
        
        if row >= 0 and col >= 0:
            # Check if drag is from task tree
            mime_data = event.mimeData()
            if mime_data.hasText():
                try:
                    task_id = int(mime_data.text())
                    if task_id in self.task_manager.tasks:
                        date = self.current_week_start.addDays(col)
                        self.task_manager.schedule_task(task_id, date.toString("yyyy-MM-dd"), str(row))
                        self.load_schedule()
                        event.accept()
                        return
                except ValueError:
                    pass
            
            # Handle drag from within schedule table (moving between slots)
            source = event.source()
            if source == self.schedule_table:
                source_row = self.schedule_table.currentRow()
                source_col = self.schedule_table.currentColumn()
                source_item = self.schedule_table.item(source_row, source_col)
                
                if source_item:
                    task_id = source_item.data(Qt.UserRole)
                    
                    # Remove from old slot
                    old_date = self.current_week_start.addDays(source_col)
                    self.task_manager.unschedule_task(old_date.toString("yyyy-MM-dd"), str(source_row))
                    
                    # Add to new slot
                    new_date = self.current_week_start.addDays(col)
                    self.task_manager.schedule_task(task_id, new_date.toString("yyyy-MM-dd"), str(row))
                    
                    self.load_schedule()
                    event.accept()
                    return
        
        event.ignore()
    
    def on_task_tree_drop(self):
        # Handle reorganization of task tree
        # This would need custom implementation to update parent_id
        pass
    
    def show_settings_dialog(self):
        dialog = SettingsDialog(self, self.slots_per_day, self.hours_per_slot)
        if dialog.exec_():
            self.slots_per_day, self.hours_per_slot = dialog.get_values()
            self.setup_schedule_table()
            self.load_schedule()
    
    def show_search_dialog(self):
        text, ok = QLineEdit().text(), True
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "Search Tasks", "Enter search keyword:")
        
        if ok and text:
            results = self.task_manager.search_tasks(text)
            if results:
                msg = "Search Results:\n\n"
                for task in results:
                    msg += f"• {task.title} ({task.state})\n"
                QMessageBox.information(self, "Search Results", msg)
            else:
                QMessageBox.information(self, "Search Results", "No tasks found")
    
    def show_notes_shortlist(self):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        results = self.task_manager.get_tasks_with_notes_in_range(start_date, end_date)
        
        if results:
            msg = "Tasks with Notes (Last 7 Days):\n\n"
            for task in results:
                msg += f"═══════════════════════════\n"
                msg += f"Task: {task.title}\n"
                msg += f"Notes: {task.notes[:200]}"
                if len(task.notes) > 200:
                    msg += "..."
                msg += "\n\n"
            QMessageBox.information(self, "Notes Shortlist", msg)
        else:
            QMessageBox.information(self, "Notes Shortlist", "No tasks with notes found in the last 7 days")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()