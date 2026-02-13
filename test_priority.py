#!/usr/bin/env python3

# Test script to verify priority ordering functionality
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TaskManager, Task

def test_priority_sorting():
    """Test that tasks are sorted by priority correctly"""
    
    # Create a temporary task manager
    tm = TaskManager("test_tasks.json")
    
    # Clear existing tasks
    tm.tasks = {}
    
    # Create test tasks with different priorities
    tasks_data = [
        ("Low Priority Task", "Low"),
        ("Critical Priority Task", "Critical"),
        ("Medium Priority Task", "Medium"),
        ("High Priority Task", "High")
    ]
    
    created_tasks = []
    for title, priority in tasks_data:
        task = Task(f"test_{title}", title, priority=priority)
        tm.tasks[task.id] = task
        created_tasks.append(task)
    
    # Test root tasks sorting
    root_tasks = tm.get_root_tasks()
    print("Root tasks sorted by priority:")
    for i, task in enumerate(root_tasks):
        print(f"{i+1}. {task.title} - {task.priority}")
    
    # Expected order: Critical, High, Medium, Low
    expected_order = ["Critical", "High", "Medium", "Low"]
    actual_order = [task.priority for task in root_tasks]
    
    if actual_order == expected_order:
        print("\n✅ Root tasks are correctly sorted by priority!")
    else:
        print(f"\n❌ Root tasks sorting failed. Expected: {expected_order}, Got: {actual_order}")
    
    # Test with sub-tasks
    parent_task = created_tasks[0]
    for title, priority in tasks_data:
        task = Task(f"sub_{title}", title, parent_id=parent_task.id, priority=priority)
        tm.tasks[task.id] = task
    
    children = tm.get_children(parent_task.id)
    print(f"\nSub-tasks of '{parent_task.title}' sorted by priority:")
    for i, task in enumerate(children):
        print(f"{i+1}. {task.title} - {task.priority}")
    
    actual_children_order = [task.priority for task in children]
    if actual_children_order == expected_order:
        print("\n✅ Sub-tasks are correctly sorted by priority!")
    else:
        print(f"\n❌ Sub-tasks sorting failed. Expected: {expected_order}, Got: {actual_children_order}")
    
    # Clean up test file
    if os.path.exists("test_tasks.json"):
        os.remove("test_tasks.json")
    
    print("\n🎉 Priority sorting test completed!")

if __name__ == "__main__":
    test_priority_sorting()
