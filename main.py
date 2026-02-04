import tkinter as tk
import queue
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import LOCAL_TEMP_BUFFER, REMOTE_SERVER_STORAGE
from services.capture_manager import CaptureManager
from services.upload_manager import UploadManager
from services.file_service import FileService
from ui.dashboard import DashboardApp
from PIL import Image, ImageFile
# Allow large images globally
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True
from utils.logger import setup_logger

logger = setup_logger("Main")

def main():
    logger.info("System Starting...")

    # 1. Setup Directories
    logger.info(f"Config: Local Buffer = {LOCAL_TEMP_BUFFER}")
    logger.info(f"Config: Remote Storage = {REMOTE_SERVER_STORAGE}")
    FileService.ensure_directory(LOCAL_TEMP_BUFFER)
    FileService.ensure_directory(REMOTE_SERVER_STORAGE)

    # 2. Shared Queue
    upload_queue = queue.Queue()

    # 3. Initialize Root UI (Needed first for callbacks usually, but we inject callbacks later)
    root = tk.Tk()

    # 4. Instantiate Business Logic
    # Forward declarations for callbacks
    app = None 

    def ui_update_cam(idx, status):
        if app:
            app.update_camera_status(idx, status)

    def ui_update_image(idx, pil_image):
        if app:
            app.update_camera_image(idx, pil_image)

    def ui_update_queue(count):
        if app:
            app.update_upload_count(count)

    capture_mgr = CaptureManager(
        upload_queue, 
        update_cam_status_callback=ui_update_cam,
        update_cam_image_callback=ui_update_image
    )
    upload_mgr = UploadManager(upload_queue, update_ui_callback=ui_update_queue)

    def on_snap():
        logger.info("UI: Snap Triggered")
        if app:
            capture_mgr.set_sn(app.get_sn())
        capture_mgr.trigger_batch_capture(save_now=False)

    def on_confirm():
        logger.info("UI: Confirm Triggered")
        if app:
            capture_mgr.set_sn(app.get_sn())
        capture_mgr.confirm_save()

    def on_retake():
        logger.info("UI: Retake Triggered")
        capture_mgr.discard_capture()

    # 5. Build UI
    app = DashboardApp(root, on_snap=on_snap, on_confirm=on_confirm, on_retake=on_retake, capture_manager=capture_mgr)

    # 6. Start Background Services
    capture_mgr.initialize_cameras()
    
    # START AUTO PREVIEW
    capture_mgr.start_preview()
    
    upload_mgr.start()

    # 7. Cleanup on Close
    def on_close():
        logger.info("Shutting down...")
        capture_mgr.shutdown()
        upload_mgr.stop()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 8. Run Message Loop
    logger.info("UI Ready. Entering Main Loop.")
    root.mainloop()

if __name__ == "__main__":
    main()
