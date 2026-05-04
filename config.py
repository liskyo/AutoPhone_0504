import os
import json
import sys

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_app_base_dir():
    """
    Return a persistent writable base directory.
    - source mode: project directory
    - frozen exe mode: folder where exe is located
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return BASE_DIR

APP_BASE_DIR = _resolve_app_base_dir()
SETTINGS_FILE = os.path.join(APP_BASE_DIR, "settings.json")

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
    },
    # Per-camera index delay before software trigger (ms). Cam i waits i * stagger.
    # Reduces GigE burst on shared switches; 0 disables. Typical 30–80; higher = slower batch.
    "capture_stagger_ms": 50,
    # MVS GetOneFrameTimeout (ms); raise if still seeing timeouts after staggering.
    "grab_frame_timeout_ms": 2000
}

def load_settings():
    """
    Return a merged copy: defaults + settings.json (file wins per key).
    Never returns the live DEFAULT_SETTINGS dict (safe to mutate result).
    """
    base = json.loads(json.dumps(DEFAULT_SETTINGS))
    if not os.path.exists(SETTINGS_FILE):
        return base
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            user = json.load(f)
        if isinstance(user, dict):
            base.update(user)
        return base
    except Exception as e:
        print(f"Error loading settings: {e}")
        return base

def save_settings(new_settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

# Load settings immediately
_current_settings = load_settings()

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
    fallback_path = os.path.join(APP_BASE_DIR, fallback_name)
    print(f"Warning: Path {preferred_path} not accessible. Using fallback: {fallback_path}")
    return fallback_path


def _apply_loaded_settings():
    """Copy _current_settings into module-level exports (initial load + reload_settings)."""
    global JPEG_QUALITY, CAMERA_COUNT, CAMERA_WIDTH, CAMERA_HEIGHT
    global RESIZE_RATIO, LOCAL_TEMP_BUFFER, REMOTE_SERVER_STORAGE, CAMERA_IPS
    global CAPTURE_STAGGER_MS, GRAB_FRAME_TIMEOUT_MS

    JPEG_QUALITY = int(_current_settings.get("jpeg_quality", 80))
    CAMERA_COUNT = int(_current_settings.get("camera_count", 5))
    CAMERA_WIDTH = int(_current_settings.get("camera_width", 5472))
    CAMERA_HEIGHT = int(_current_settings.get("camera_height", 3648))
    RESIZE_RATIO = int(_current_settings.get("resize_ratio", 80))

    LOCAL_TEMP_BUFFER = _current_settings.get(
        "local_temp_buffer", r"C:\Users\W00273\Downloads\AutoPhote"
    )
    REMOTE_SERVER_STORAGE = get_valid_path(
        _current_settings.get(
            "remote_server_storage", r"T:\0000 資料共用暫存區\測試照片區"
        ),
        "Server_Storage",
    )

    _raw_ips = _current_settings.get("camera_ips", {})
    CAMERA_IPS = {int(k): v for k, v in _raw_ips.items()}

    CAPTURE_STAGGER_MS = int(_current_settings.get("capture_stagger_ms", 100))
    GRAB_FRAME_TIMEOUT_MS = int(_current_settings.get("grab_frame_timeout_ms", 2000))


def reload_settings():
    """
    Re-read settings.json into module-level variables (no process restart).
    Next capture / upload / grab timeout use new values.
    Changing camera count or IP still needs app restart to reconnect and refresh UI grid.
    """
    global _current_settings
    _current_settings = load_settings()
    _apply_loaded_settings()


_apply_loaded_settings()

# Hardware Interface Settings
USE_REAL_CAMERA = True
#USE_REAL_CAMERA = False  # Set to True when connecting real cameras

# UI Settings
UI_PREVIEW_WIDTH = 360
UI_PREVIEW_HEIGHT = 200

# Upload Settings
UPLOAD_RETRY_DELAY = 2  # seconds
MAX_RETRIES = 3
