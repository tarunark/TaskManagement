#!/usr/bin/env python3

# Create test tasks with different priorities to demonstrate the functionality
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TaskManager

def create_demo_tasks():
    """Create demo tasks with different priorities"""
    
    # Load existing task manager
    tm = TaskManager()
    
    # Create test tasks with different priorities
    demo_tasks = [
        ("Critical Task", "Critical", None),
        ("High Priority Task", "High", None),
        ("Low Priority Task", "Low", None),
        ("Another Medium Task", "Medium", None),
        ("Subtask of Critical", "Low", None),  # Will be updated to child of critical
        ("Subtask of High", "High", None),     # Will be updated to child of high
    ]
    
    print("Creating demo tasks with different priorities...")
    
    created_tasks = []
    for title, priority, parent_id in demo_tasks:
        task = tm.create_task(title, parent_id=parent_id, priority=priority)
        created_tasks.append(task)
        print(f"Created: {title} - {priority}")
    
    # Update some tasks to have children
    if len(created_tasks) >= 6:
        # Make task 4 a child of task 0 (Critical)
        tm.update_task(created_tasks[4].id, parent_id=created_tasks[0].id, save=False)
        # Make task 5 a child of task 1 (High)
        tm.update_task(created_tasks[5].id, parent_id=created_tasks[1].id, save=False)
        tm.save_data()
    
    print("\n✅ Demo tasks created successfully!")
    print("Run the main application to see the priority-based ordering in action.")
    print("\nFeatures available:")
    print("- Tasks are now sorted by priority (Critical > High > Medium > Low)")
    print("- Right-click on tasks to see 'Change Priority' submenu")
    print("- Use Ctrl+1 (Low), Ctrl+2 (Medium), Ctrl+3 (High), Ctrl+4 (Critical) for quick priority changes")
    print("- Task titles are color-coded by priority")

if __name__ == "__main__":
    create_demo_tasks()
