import json
import os

TODO_FILE = "todo.json"

def load_list():
    """
    Loads the to-do list from a JSON file.
    
    Returns:
        list: The loaded to-do list.
    """
    if os.path.exists(TODO_FILE):
        try:
            with open(TODO_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_list(todo_list):
    """
    Saves the to-do list to a JSON file.
    
    Args:
        todo_list (list): The to-do list to save.
    """
    with open(TODO_FILE, 'w') as f:
        json.dump(todo_list, f, indent=4)

def create_list():
    """
    Creates/Loads the to-do list.

    Returns:
        list: The to-do list.
    """
    return load_list()

def add_task(task):
    """
    Adds a task to the to-do list.

    Args:
        task (str): The task to add.
    """
    todo_list = load_list()
    todo_list.append(task)
    save_list(todo_list)
    return f"Task '{task}' added to the to-do list."

def delete_task(task):
    """
    Deletes a task from the to-do list.

    Args:
        task (str): The task to delete.
    """
    todo_list = load_list()
    if task in todo_list:
        todo_list.remove(task)
        save_list(todo_list)
        return f"Task '{task}' removed from the to-do list."
    else:
        return f"Task '{task}' not found in the to-do list."

def display_todo_list():
    """
    Returns the current to-do list as a string.
    """
    todo_list = load_list()
    if not todo_list:
        return "Your to-do list is empty."
    else:
        result = "Your to-do list:\n"
        for i, task in enumerate(todo_list):
            result += f"{i+1}. {task}\n"
        return result

if __name__ == "__main__":
    print(add_task("Test Task"))
    print(display_todo_list())
    print(delete_task("Test Task"))
    print(display_todo_list())
