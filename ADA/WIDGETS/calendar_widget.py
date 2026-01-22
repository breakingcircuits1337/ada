import json
import os
from datetime import datetime

CALENDAR_FILE = "calendar.json"

def load_events():
    """
    Loads events from the JSON file.
    """
    if os.path.exists(CALENDAR_FILE):
        try:
            with open(CALENDAR_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_events(events):
    """
    Saves events to the JSON file.
    """
    with open(CALENDAR_FILE, 'w') as f:
        json.dump(events, f, indent=4)

def add_event(title, date_str, time_str, description=""):
    """
    Adds an event to the calendar.

    Args:
        title (str): Title of the event.
        date_str (str): Date in YYYY-MM-DD format.
        time_str (str): Time in HH:MM format.
        description (str): Optional description.
    """
    events = load_events()
    
    # Basic validation
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return "Error: Date must be YYYY-MM-DD and time must be HH:MM."

    new_event = {
        "title": title,
        "date": date_str,
        "time": time_str,
        "description": description,
        "created_at": datetime.now().isoformat()
    }
    
    events.append(new_event)
    # Sort events by date and time
    events.sort(key=lambda x: (x['date'], x['time']))
    
    save_events(events)
    return f"Event '{title}' added for {date_str} at {time_str}."

def list_events(date_str=None):
    """
    Lists events. If date_str is provided, lists events for that date.
    Otherwise, lists upcoming events.

    Args:
        date_str (str): Optional. Date in YYYY-MM-DD format.
    """
    events = load_events()
    if not events:
        return "Calendar is empty."

    output = []
    if date_str:
        output.append(f"Events for {date_str}:")
        filtered_events = [e for e in events if e['date'] == date_str]
    else:
        output.append("Upcoming Events:")
        # Filter for today onwards? For now just list all
        filtered_events = events

    if not filtered_events:
        return "No events found."

    for event in filtered_events:
        output.append(f"- [{event['date']} {event['time']}] {event['title']}: {event['description']}")
    
    return "\n".join(output)

def delete_event(title):
    """
    Deletes an event by title.
    """
    events = load_events()
    initial_count = len(events)
    events = [e for e in events if e['title'].lower() != title.lower()]
    
    if len(events) < initial_count:
        save_events(events)
        return f"Event '{title}' deleted."
    else:
        return f"Event '{title}' not found."

if __name__ == "__main__":
    # Test
    print(add_event("Team Meeting", "2023-10-27", "14:00", "Discuss project roadmap"))
    print(list_events())
