import time
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import threading
from utils.logger import setup_logger

logger = setup_logger("Hardware")

class CameraBase:
    def connect(self):
        raise NotImplementedError
    
    def disconnect(self):
        raise NotImplementedError

    def grab_image(self):
        raise NotImplementedError

class MockCamera(CameraBase):
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.connected = False
        
    def connect(self):
        time.sleep(0.1)  # Simulate init time
        self.connected = True
        logger.info(f"Camera {self.camera_id} connected.")
        return True

    def disconnect(self):
        self.connected = False
        logger.info(f"Camera {self.camera_id} disconnected.")

    def grab_image(self):
        """
        Simulate grabbing an image.
        Returns: PIL Image object
        """
        if not self.connected:
            raise Exception(f"Camera {self.camera_id} is not connected!")

        # Simulate exposure time
        time.sleep(random.uniform(0.05, 0.2))

        # Create a generated image (Noise + Text)
        width, height = 5472, 3648
        # Random noise background
        arr = np.random.randint(0, 50, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(arr, 'RGB')
        
        # Draw Text
        draw = ImageDraw.Draw(img)
        # Try to use a default font
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        text = f"CAM ID: {self.camera_id}\nTime: {timestamp}\nLot: MOCK-001"
        
        draw.text((10, 10), text, fill=(0, 255, 0), font=font)
        
        return img
