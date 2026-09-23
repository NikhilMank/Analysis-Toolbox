import json
import os

# Get the absolute path to the root folder (one level up from the 'utils' folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')

DEFAULT_SETTINGS = {
    "last_opened_folder": os.path.expanduser("~"),  # Defaults to the user's home directory
    "theme": "System",
    "language": "en"
}

def load_settings():
    """Loads settings from the JSON file. Creates defaults if missing."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
        
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # If the file is corrupted or unreadable, fall back to defaults safely
        return DEFAULT_SETTINGS

def save_settings(settings):
    """Saves the provided settings dictionary to the JSON file."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def update_setting(key, value):
    """Updates a single setting key and saves the file."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
    
def get_setting(key):
    """Retrieves a single setting. Returns the default value if the key is not found."""
    settings = load_settings()
    return settings.get(key, DEFAULT_SETTINGS.get(key))