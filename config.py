import os
import json

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Default settings if json is missing
DEFAULT_SETTINGS = {
    "camera_count": 5,
    "camera_width": 5472,
    "camera_height": 3648,
    "resize_ratio": 80, # Percentage (10-100)
    "jpeg_quality": 80,
    "local_temp_buffer": r"C:\Users\W00273\Downloads\AutoPhote",
    "remote_server_storage": r"T:\0000 資料共用暫存區\測試照片區",
    "camera_ips": {
        "1": "192.168.1.101",
        "2": "192.168.1.102",
        "3": "192.168.1.103",
        "4": "192.168.1.104",
        "5": "192.168.1.105"
    }
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS

def save_settings(new_settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

# Load settings immediately
_current_settings = load_settings()

JPEG_QUALITY = _current_settings.get("jpeg_quality", 80)

# Helper to check if drive exists
def get_valid_path(preferred_path, fallback_name):
    # Check if the drive/root of the preferred path exists
    drive = os.path.splitdrive(preferred_path)[0]
    if drive and os.path.exists(drive):
        return preferred_path
    
    # Special handling: If path is just a local absolute path that is valid
    if os.path.isabs(preferred_path) and os.path.exists(os.path.dirname(preferred_path)):
        return preferred_path
        
    # Fallback to project directory
    fallback_path = os.path.join(BASE_DIR, fallback_name)
    print(f"Warning: Path {preferred_path} not accessible. Using fallback: {fallback_path}")
    return fallback_path

# Export variables (mapped from settings)
CAMERA_COUNT = int(_current_settings.get("camera_count", 5))
CAMERA_WIDTH = int(_current_settings.get("camera_width", 5472))
CAMERA_HEIGHT = int(_current_settings.get("camera_height", 3648))
RESIZE_RATIO = int(_current_settings.get("resize_ratio", 80))

# Storage Paths
LOCAL_TEMP_BUFFER = _current_settings.get("local_temp_buffer", r"C:\Users\W00273\Downloads\AutoPhote")
REMOTE_SERVER_STORAGE = get_valid_path(_current_settings.get("remote_server_storage", r"T:\0000 資料共用暫存區\測試照片區"), "Server_Storage")

# Camera IP Configuration
# Ensure keys are integers for code compatibility if JSON loaded them as strings
_raw_ips = _current_settings.get("camera_ips", {})
CAMERA_IPS = {int(k): v for k, v in _raw_ips.items()}

# Hardware Interface Settings
USE_REAL_CAMERA = True
#USE_REAL_CAMERA = False  # Set to True when connecting real cameras

# UI Settings
UI_PREVIEW_WIDTH = 360
UI_PREVIEW_HEIGHT = 200

# Upload Settings
UPLOAD_RETRY_DELAY = 2  # seconds
MAX_RETRIES = 3
