
import sys
SDK_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
print(f"Adding {SDK_PATH}")
sys.path.append(SDK_PATH)
try:
    print("Importing MvCameraControl_class...")
    import MvCameraControl_class
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
