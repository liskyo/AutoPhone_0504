import time
import queue
import threading
import os
import config
from config import UPLOAD_RETRY_DELAY, MAX_RETRIES
from services.file_service import FileService
from utils.logger import setup_logger

logger = setup_logger("UploadService")

class UploadManager:
    def __init__(self, upload_queue, update_ui_callback=None):
        self.upload_queue = upload_queue
        self.running = False
        self.thread = None
        self.update_ui_callback = update_ui_callback # Function to call to update UI count

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._process_queue, daemon=True)
        self.thread.start()
        logger.info("Upload Manager started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Upload Manager stopped.")

    def _process_queue(self):
        while self.running:
            try:
                # Wait for file path from queue
                # timeout allows checking self.running periodically
                file_path = self.upload_queue.get(timeout=1) 
                
                if file_path is None:
                    continue

                self._handle_upload(file_path)
                self.upload_queue.task_done()
                
                if self.update_ui_callback:
                    self.update_ui_callback(self.upload_queue.qsize())

            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Unexpected error in upload loop: {e}")

    def _handle_upload(self, file_path):
        attempt = 0
        success = False
        dest_folder = config.REMOTE_SERVER_STORAGE
        try:
            buf = os.path.normpath(config.LOCAL_TEMP_BUFFER)
            dirname = os.path.normpath(os.path.dirname(file_path))
            try:
                if os.path.commonpath([buf, dirname]) == buf:
                    rel = os.path.relpath(dirname, buf)
                    if rel and rel != ".":
                        dest_folder = os.path.join(config.REMOTE_SERVER_STORAGE, *rel.split(os.sep))
            except ValueError:
                pass
            if dest_folder == config.REMOTE_SERVER_STORAGE:
                local_parent = os.path.basename(os.path.dirname(file_path))
                if local_parent:
                    dest_folder = os.path.join(config.REMOTE_SERVER_STORAGE, local_parent)
        except Exception as e:
            logger.warning(f"Failed to resolve remote subfolder: {e}")
        FileService.ensure_directory(dest_folder)
        
        while attempt < MAX_RETRIES and not success:
            logger.info(f"Uploading {file_path} (Attempt {attempt+1}/{MAX_RETRIES})...")
            
            # Brief pause between retries (was 0.5s; shorter feels more responsive locally)
            time.sleep(0.15)
            
            # Try copying file (Keep local)
            if FileService.copy_file(file_path, dest_folder):
                success = True
                logger.info(f"Upload success (Copied): {file_path}")
            else:
                attempt += 1
                logger.warning(f"Upload failed. Retrying in {UPLOAD_RETRY_DELAY}s...")
                time.sleep(UPLOAD_RETRY_DELAY)
        
        if not success:
            logger.error(f"Final failure uploading {file_path}. Keeping locally.")
            # Depending on requirements, we might move to a 'failed' folder or alert UI.
