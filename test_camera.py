
import sys
import os
import time
import ctypes
from ctypes import *

# --- SDK Path Setup ---
SDK_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
sys.path.append(SDK_PATH)

try:
    from MvCameraControl_class import *
    print("SDK loaded successfully.")
except ImportError:
    print(f"Error: Could not import MVS SDK from {SDK_PATH}")
    sys.exit(1)

def main():
    print("Searching for devices...")
    
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print(f"Enum Devices failed! ret=0x{ret:x}")
        sys.exit(1)

    n_devices = deviceList.nDeviceNum
    print(f"Found {n_devices} devices.")
    
    if n_devices == 0:
        print("No cameras found. Check connection and power.")
        sys.exit(0)

    target_device = None
    target_ip = "192.168.1.101"  # The IP we want to match our config

    for i in range(n_devices):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        
        # Print basic info
        print(f"\n--- Device {i} ---")
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                if per == 0: break
                strModeName = strModeName + chr(per)
            
            nip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
            ip_str = f"{(nip >> 24) & 0xFF}.{(nip >> 16) & 0xFF}.{(nip >> 8) & 0xFF}.{nip & 0xFF}"
            print(f"Model: {strModeName}")
            print(f"Current IP: {ip_str}")
            
            if ip_str == target_ip:
                print(f"Match found! Will verify connection to {ip_str}")
                target_device = mvcc_dev_info

    # If we didn't find exact match, try the first one purely for testing connectivity
    if target_device is None:
        print(f"\nTarget IP {target_ip} not found. Attempting to connect to the first available camera for testing...")
        target_device = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

    # Connect
    cam = MvCamera()
    ret = cam.MV_CC_CreateHandle(target_device)
    if ret != 0:
        print(f"Create Handle failed! ret=0x{ret:x}")
        return

    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"Open Device failed! ret=0x{ret:x}")
        print("Hint: Check if IP is in the same subnet as PC, or if used by another program.")
        return
    
    print("Camera Open Success!")
    
    # Get Payload Size
    stParam = MVCC_INTVALUE()
    memset(byref(stParam), 0, sizeof(MVCC_INTVALUE))
    ret = cam.MV_CC_GetIntValue("PayloadSize", stParam)
    if ret != 0:
        print("Get PayloadSize failed")
    nPayloadSize = stParam.nCurValue

    # Start Grabbing
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("Start Grabbing failed")
    
    # Try one frame
    pData = (c_ubyte * nPayloadSize)()
    stFrameInfo = MV_FRAME_OUT_INFO_EX()
    memset(byref(stFrameInfo), 0, sizeof(MV_FRAME_OUT_INFO_EX))

    print("Capturing 1 frame...")
    ret = cam.MV_CC_GetOneFrameTimeout(byref(pData), nPayloadSize, stFrameInfo, 1000)
    if ret == 0:
        print(f"Frame Captured! Size: {stFrameInfo.nWidth}x{stFrameInfo.nHeight}")
        print("Test successful.")
    else:
        print(f"GetOneFrame failed! ret=0x{ret:x}")

    # Cleanup
    cam.MV_CC_StopGrabbing()
    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()

if __name__ == "__main__":
    main()
