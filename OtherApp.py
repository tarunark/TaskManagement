import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLineEdit, QPushButton, QInputDialog, QMessageBox)
from PyQt5.QtCore import Qt


class TaskTreeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.all_items = []  # Store all items for filtering
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Task Manager with Search')
        self.setGeometry(100, 100, 600, 500)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Search field
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText('Type to filter tasks...')
        self.search_field.textChanged.connect(self.filter_tasks)
        layout.addWidget(self.search_field)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Task'])
        self.tree.setColumnCount(1)
        layout.addWidget(self.tree)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        add_task_btn = QPushButton('Add Task')
        add_task_btn.clicked.connect(self.add_task)
        button_layout.addWidget(add_task_btn)
        
        add_subtask_btn = QPushButton('Add Subtask')
        add_subtask_btn.clicked.connect(self.add_subtask)
        button_layout.addWidget(add_subtask_btn)
        
        remove_btn = QPushButton('Remove Task')
        remove_btn.clicked.connect(self.remove_task)
        button_layout.addWidget(remove_btn)
        
        layout.addLayout(button_layout)
        
        # Add some sample tasks
        self.add_sample_tasks()
        
    def add_sample_tasks(self):
        """Add initial sample tasks"""
        task1 = QTreeWidgetItem(self.tree, ['Complete project documentation'])
        task2 = QTreeWidgetItem(self.tree, ['Review code'])
        task3 = QTreeWidgetItem(self.tree, ['Plan sprint meeting'])
        
        # Add subtasks
        QTreeWidgetItem(task1, ['Write user guide'])
        QTreeWidgetItem(task1, ['Create API documentation'])
        QTreeWidgetItem(task2, ['Check Python files'])
        
        self.tree.expandAll()
        self.rebuild_item_list()
        
    def add_task(self):
        """Add a new top-level task"""
        text, ok = QInputDialog.getText(self, 'Add Task', 'Enter task name:')
        if ok and text:
            item = QTreeWidgetItem(self.tree, [text])
            self.rebuild_item_list()
            self.filter_tasks(self.search_field.text())
            
    def add_subtask(self):
        """Add a subtask to the selected task"""
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, 'No Selection', 'Please select a task first.')
            return
            
        text, ok = QInputDialog.getText(self, 'Add Subtask', 'Enter subtask name:')
        if ok and text:
            parent = selected[0]
            item = QTreeWidgetItem(parent, [text])
            parent.setExpanded(True)
            self.rebuild_item_list()
            self.filter_tasks(self.search_field.text())
            
    def remove_task(self):
        """Remove the selected task"""
        selected = self.tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, 'No Selection', 'Please select a task to remove.')
            return
            
        item = selected[0]
        parent = item.parent()
        
        if parent:
            parent.removeChild(item)
        else:
            index = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(index)
            
        self.rebuild_item_list()
        self.filter_tasks(self.search_field.text())
        
    def rebuild_item_list(self):
        """Rebuild the list of all items for filtering"""
        self.all_items = []
        
        def collect_items(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                self.all_items.append({
                    'item': child,
                    'text': child.text(0),
                    'parent': parent
                })
                collect_items(child)
        
        # Collect top-level items
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self.all_items.append({
                'item': item,
                'text': item.text(0),
                'parent': None
            })
            collect_items(item)
            
    def filter_tasks(self, search_text):
        """Filter tree items based on search text"""
        search_text = search_text.lower()
        
        def set_visibility(item, visible):
            """Recursively set visibility of item and children"""
            item.setHidden(not visible)
            for i in range(item.childCount()):
                set_visibility(item.child(i), visible)
        
        def check_match(item):
            """Check if item or any child matches search"""
            text_match = search_text in item.text(0).lower()
            
            # Check children
            child_match = False
            for i in range(item.childCount()):
                if check_match(item.child(i)):
                    child_match = True
            
            # Show if this item or any child matches
            is_visible = text_match or child_match
            item.setHidden(not is_visible)
            
            # Expand if children are visible
            if child_match:
                item.setExpanded(True)
            
            return is_visible
        
        # If search is empty, show everything
        if not search_text:
            for i in range(self.tree.topLevelItemCount()):
                set_visibility(self.tree.topLevelItem(i), True)
        else:
            # Check each top-level item
            for i in range(self.tree.topLevelItemCount()):
                check_match(self.tree.topLevelItem(i))


def main():
    app = QApplication(sys.argv)
    window = TaskTreeApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()