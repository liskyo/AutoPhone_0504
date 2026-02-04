
print("DEBUG: 1. Start")
import sys
import os
print("DEBUG: 2. Basic imports done")

try:
    print("DEBUG: 3. Importing config")
    from config import LOCAL_TEMP_BUFFER, USE_REAL_CAMERA
    print(f"DEBUG: 3. Config done. Use Real Cam: {USE_REAL_CAMERA}")
except Exception as e:
    print(f"DEBUG: 3. Config Failed: {e}")

try:
    print("DEBUG: 4. Importing CaptureManager")
    from services.capture_manager import CaptureManager
    print("DEBUG: 4. CaptureManager imported")
except Exception as e:
    print(f"DEBUG: 4. CaptureManager Failed: {e}")

try:
    print("DEBUG: 5. Importing HikCamera (Directly)")
    from hardware.hik_camera import HikCamera
    print("DEBUG: 5. HikCamera imported")
except Exception as e:
    print(f"DEBUG: 5. HikCamera Failed: {e}")

print("DEBUG: 6. Test Done")
