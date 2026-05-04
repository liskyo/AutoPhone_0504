import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor
import config
from hardware.mock_camera import MockCamera
from hardware.hik_camera import HikCamera
from services.file_service import FileService
from utils.logger import setup_logger
from utils.image_utils import overlay_timestamp

logger = setup_logger("CaptureService")

class CaptureManager:
    def __init__(self, upload_queue, update_cam_status_callback=None, update_cam_image_callback=None):
        self.cameras = []
        self.upload_queue = upload_queue
        self.executor = ThreadPoolExecutor(max_workers=config.CAMERA_COUNT)
        self.update_cam_status_callback = update_cam_status_callback 
        self.update_cam_image_callback = update_cam_image_callback # callback(cam_idx, pil_image)
        self.pending_captures = {} # {index: pil_image}
        self.sn_code = ""
        self.serial_date = ""
        self.serial_counter = 0
        self.serial_lock = threading.Lock()
        # Status codes: 0=Disconnected, 1=Connected, 2=Capturing, 3=Done/Success, 4=Error, 5=Reviewing

    def initialize_cameras(self):
        logger.info(f"Initializing {config.CAMERA_COUNT} cameras... (Real Hardware: {config.USE_REAL_CAMERA})")
        for i in range(config.CAMERA_COUNT):
            if config.USE_REAL_CAMERA:
                ip = config.CAMERA_IPS.get(i+1, "0.0.0.0")
                cam = HikCamera(camera_id=i+1, ip_address=ip)
            else:
                cam = MockCamera(camera_id=i+1)
            
            if cam.connect():
                self.cameras.append(cam)
                if self.update_cam_status_callback:
                    self.update_cam_status_callback(i, 1) # Connected
            else:
                logger.error(f"Failed to connect to Camera {i+1}")
                if self.update_cam_status_callback:
                    self.update_cam_status_callback(i, 0) # Error
        logger.info("All cameras initialized.")

    def trigger_batch_capture(self, save_now=True):
        """
        Trigger all cameras.
        If save_now is False, images are stored in pending_captures for review.
        """
        logger.info(f"Trigger received! Batch capture (Save={save_now}).")
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        date_str = time.strftime("%Y%m%d")
        self.pending_captures.clear()
        
        futures = []
        for i, cam in enumerate(self.cameras):
            if self.update_cam_status_callback:
                self.update_cam_status_callback(i, 2) # Capturing
            futures.append(self.executor.submit(self._capture_task, cam, i, timestamp_str, save_now))
        
        if save_now:
            def wait_and_reset():
                for f in futures:
                    try:
                        f.result()
                    except Exception:
                        pass
                self._reset_serial(date_str)
            threading.Thread(target=wait_and_reset, daemon=True).start()

    def _capture_task(self, camera, index, batch_id, save_now):
        try:
            # Stagger inside worker threads so GigE frames (esp. shared switch uplink)
            # do not all hit the wire at once; does not block Tk main thread.
            stagger_ms = max(0, int(config.CAPTURE_STAGGER_MS))
            if stagger_ms > 0 and index > 0:
                delay_s = (index * stagger_ms) / 1000.0
                if delay_s > 0:
                    time.sleep(delay_s)

            img = camera.grab_image()
            logger.debug(f"Cam {index+1} Grab success. Type: {type(img)}")
            
            # --- OVERLAY TIMESTAMP ---
            try:
                img = overlay_timestamp(img, camera_id=index+1)
                logger.debug(f"Cam {index+1} Overlay success.")
            except Exception as e_overlay:
                logger.error(f"Cam {index+1} Overlay failed: {e_overlay}")
                # Continue without overlay if it fails
                pass

            # Update UI immediately for preview
            if self.update_cam_image_callback:
                self.update_cam_image_callback(index, img)

            if not save_now:
                # Store for review
                self.pending_captures[index] = img
                if self.update_cam_status_callback:
                    self.update_cam_status_callback(index, 5) # Reviewing
                return

            # Save immediately
            self._save_and_queue(index, img, batch_id)
                    
        except Exception as e:
            logger.error(f"Error capturing from Cam {index+1}: {e}")
            if self.update_cam_status_callback:
                self.update_cam_status_callback(index, 4) # Exception

    def confirm_save(self):
        """
        Save all pending captures to disk and queue for upload.
        """
        logger.info("Confirming save for pending captures...")
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        date_str = time.strftime("%Y%m%d")
        
        # We can run this in parallel too, but simple loop is fine for saving
        for index, img in self.pending_captures.items():
            try:
                self._save_and_queue(index, img, timestamp_str)
            except Exception as e:
                logger.error(f"Error saving pending Cam {index+1}: {e}")
                self.update_cam_status_callback(index, 4)

        self.pending_captures.clear()
        self._reset_serial(date_str)

    def discard_capture(self):
        """
        Discard pending captures and reset status to Ready.
        """
        logger.info("Discarding pending captures.")
        self.pending_captures.clear()
        for i in range(len(self.cameras)):
             if self.update_cam_status_callback:
                self.update_cam_status_callback(i, 1) # Reset to Ready

    def set_sn(self, sn_code):
        self.sn_code = (sn_code or "").strip()

    def _reset_serial(self, date_str):
        with self.serial_lock:
            self.serial_date = date_str
            self.serial_counter = 0

    def _get_sn_and_folder(self):
        date_str = time.strftime("%Y%m%d")
        sn = self.sn_code.strip() if self.sn_code else "UNKNOWN"
        folder_name = f"{sn}_{date_str}"
        folder_path = os.path.join(config.LOCAL_TEMP_BUFFER, folder_name)
        return sn, date_str, folder_path

    def _next_filename(self, sn, date_str, folder_path):
        FileService.ensure_directory(folder_path)
        with self.serial_lock:
            if self.serial_date != date_str:
                self.serial_date = date_str
                self.serial_counter = 0
            serial = self.serial_counter + 1
            while True:
                filename = f"{sn}_{date_str}_{serial:03d}.jpg"
                filepath = os.path.join(folder_path, filename)
                if not os.path.exists(filepath):
                    self.serial_counter = serial
                    return filename
                serial += 1

    def _save_and_queue(self, index, img, batch_id):
        # Apply Resizing if needed
        if config.RESIZE_RATIO < 100:
             try:
                # Calculate new size
                w, h = img.size
                new_w = int(w * (config.RESIZE_RATIO / 100.0))
                new_h = int(h * (config.RESIZE_RATIO / 100.0))
                logger.debug(f"Resizing Cam {index+1} from {w}x{h} to {new_w}x{new_h} ({config.RESIZE_RATIO}%)")
                
                # Use PIL's resize for better quality control than thumbnail in this context
                # (LANCZOS is good for downsampling)
                from PIL import Image
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
             except Exception as e:
                logger.error(f"Resize failed for Cam {index+1}: {e}")

        sn, date_str, folder_path = self._get_sn_and_folder()
        filename = self._next_filename(sn, date_str, folder_path)
        saved_path = FileService.save_image(img, folder_path, filename, quality=config.JPEG_QUALITY)
        
        if saved_path:
            self.upload_queue.put(saved_path)
            logger.debug(f"Cam {index+1} captured & queued.")
            if self.update_cam_status_callback:
                self.update_cam_status_callback(index, 3) # Success
        else:
            if self.update_cam_status_callback:
                self.update_cam_status_callback(index, 4) # Save Error

    def start_preview(self):
        """
        Start live preview for all connected cameras.
        """
        logger.info("Starting live preview for all cameras...")
        
        def preview_callback(cam_id, img):
            # Map camera_id (1-based) to index (0-based) for UI callback
            if self.update_cam_image_callback:
                idx = cam_id - 1
                self.update_cam_image_callback(idx, img)

        for cam in self.cameras:
            if isinstance(cam, HikCamera): # Or MockCamera if it supported streaming
                cam.start_streaming(preview_callback)

    def stop_preview(self):
        """
        Stop live preview for all cameras.
        """
        logger.info("Stopping live preview...")
        for cam in self.cameras:
            if hasattr(cam, 'stop_streaming'): # Safety check
                cam.stop_streaming()

    def shutdown(self):
        self.stop_preview()
        for cam in self.cameras:
            cam.disconnect()
        self.executor.shutdown(wait=True)
