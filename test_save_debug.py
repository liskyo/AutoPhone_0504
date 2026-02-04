
import sys
import os
import platform
import numpy as np
from PIL import Image, ImageFile

# Configure PIL
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True
ImageFile.MAXBLOCK = 65536 * 1024

def test_save():
    print(f"Python Version: {sys.version}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Max Size: {sys.maxsize}")
    
    width = 5472
    height = 3648
    print(f"Creating test image {width}x{height} (RGB)...")
    
    try:
        # Create random noise data
        # data = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        # Using zeros is faster and uses less memory allocation overhead during creation
        data = np.zeros((height, width, 3), dtype=np.uint8)
        # Add some patterns
        data[::100, ::100] = [255, 0, 0]
        
        print(f"Numpy array created. Shape: {data.shape}, Type: {data.dtype}")
        
        img = Image.fromarray(data, 'RGB')
        print("PIL Image created.")
        
        # Test JPEG
        print("Saving JPEG...")
        img.save("test_debug_20mp.jpg", quality=95)
        print("JPEG Saved Successfully.")
        
        # Test PNG
        print("Saving PNG...")
        # Increase block for PNG too just in case
        img.save("test_debug_20mp.png")
        print("PNG Saved Successfully.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"TEST FAILED: {e}")

if __name__ == "__main__":
    test_save()
