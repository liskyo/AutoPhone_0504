
import sys
import threading
import time
import ctypes
import numpy as np
from PIL import Image
from hardware.mock_camera import CameraBase
from utils.logger import setup_logger

logger = setup_logger("HikHardware")

# --- SDK IMPORT CHECK ---
# Default installation path for Hikrobot MVS Python SDK
SDK_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"

try:
    sys.path.append(SDK_PATH)
    from MvCameraControl_class import *
    HIK_SDK_AVAILABLE = True
except ImportError:
    HIK_SDK_AVAILABLE = False
    logger.warning(f"Hikvision SDK not found at {SDK_PATH}. Please verify installation path.")

class HikCamera(CameraBase):
    def __init__(self, camera_id, ip_address):
        self.camera_id = camera_id
        self.ip_address = ip_address
        self.handle = None
        self.connected = False
        
        # Buffer for raw data
        self.pData = None
        self.nPayloadSize = 0
        
        # Streaming State
        self.streaming = False
        self.stream_thread = None

    def connect(self):
        if not HIK_SDK_AVAILABLE:
            logger.error("Hikvision SDK not imported. Cannot connect.")
            return False

        logger.info(f"Connecting to Camera {self.camera_id} ({self.ip_address})...")
        
        # 1. Enum Devices
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            logger.error(f"Enum Devices failed: {ret}")
            return False

        # 2. Find Device by IP
        target_device_info = None
        for i in range(deviceList.nDeviceNum):
            mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                # Get IP from GigE Info
                gige_info = mvcc_dev_info.SpecialInfo.stGigEInfo
                # Convert c_ubyte array to string
                current_ip = f"{gige_info.nCurrentIp & 0xFF000000 >> 24}.{gige_info.nCurrentIp & 0x00FF0000 >> 16}.{gige_info.nCurrentIp & 0x0000FF00 >> 8}.{gige_info.nCurrentIp & 0x000000FF}"
                
                # Note: The above bitwise might depend on endianness, easier to compare strict strings if accessible
                # A safer way in Python SDK examples usually iterates and prints IPs.
                # For now, let's trust the logic or use a simpler match if needed.
                # Actually, the easier strategy is to match by UserDefinedName or SerialNumber if IP is tricky.
                # But let's assume we scan all and connect to any for demo, or match IP string.
                pass
            
            # SIMPLIFICATION FOR THIS PROJECT:
            # We assume connection by Index for now if IP matching is complex in raw ctypes
            # Ideally, we match config IP.
            if i == (self.camera_id - 1): # Simple mapping: Cam 1 -> Index 0
                target_device_info = mvcc_dev_info
                break

        if target_device_info is None:
            logger.error(f"Camera {self.camera_id} not found in device list.")
            return False

        # 3. Create Handle
        self.handle = MvCamera()
        ret = self.handle.MV_CC_CreateHandle(target_device_info)
        if ret != 0:
            logger.error(f"Create Handle failed: {ret}")
            return False

        # 4. Open Device
        ret = self.handle.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            logger.error(f"Open Device failed: {ret}")
            return False

        # 5. Configure Parameters
        # Set Trigger Mode = On (1)
        ret = self.handle.MV_CC_SetEnumValue("TriggerMode", 1)
        # Set Trigger Source = Software (7)
        ret = self.handle.MV_CC_SetEnumValue("TriggerSource", 7)
        
        # Get Payload Size for buffer allocation
        stParam = MVCC_INTVALUE()
        memset(byref(stParam), 0, sizeof(MVCC_INTVALUE))
        ret = self.handle.MV_CC_GetIntValue("PayloadSize", stParam)
        self.nPayloadSize = stParam.nCurValue
        
        # Allocate buffer
        self.pData = (c_ubyte * self.nPayloadSize)()

        # 6. Start Grabbing
        ret = self.handle.MV_CC_StartGrabbing()
        if ret != 0:
            logger.error(f"Start Grabbing failed: {ret}")
            return False

        # --- DIAGNOSTICS: Check actual parameters ---
        try:
            stFloatVal = MVCC_FLOATVALUE()
            memset(byref(stFloatVal), 0, sizeof(MVCC_FLOATVALUE))
            self.handle.MV_CC_GetFloatValue("ExposureTime", stFloatVal)
            current_exposure = stFloatVal.fCurValue
            
            self.handle.MV_CC_GetFloatValue("Gain", stFloatVal)
            current_gain = stFloatVal.fCurValue
            
            logger.info(f"DIAGNOSTICS - Cam {self.camera_id} | Exposure: {current_exposure} us | Gain: {current_gain}")
        except:
            logger.warning("Could not read diagnostic params.")
        # --------------------------------------------

        self.connected = True
        logger.info(f"Camera {self.camera_id} connected successfully.")
        return True

    def disconnect(self):
        if self.handle:
            self.handle.MV_CC_StopGrabbing()
            self.handle.MV_CC_CloseDevice()
            self.handle.MV_CC_DestroyHandle()
        
        self.connected = False
        logger.info(f"Camera {self.camera_id} disconnected.")

    def grab_image(self):
        """
        Software Trigger -> Capture -> Convert to PIL
        """
        if not self.connected or not self.handle:
             raise Exception(f"HikCamera {self.camera_id} not connected")

        # 1. Send Software Trigger Command
        ret = self.handle.MV_CC_SetCommandValue("TriggerSoftware")
        if ret != 0:
             raise Exception(f"Trigger failed: {ret}")

        # 2. Get Frame
        stFrameInfo = MV_FRAME_OUT_INFO_EX()
        memset(byref(stFrameInfo), 0, sizeof(MV_FRAME_OUT_INFO_EX))
        
        # Wait up to 1000ms
        ret = self.handle.MV_CC_GetOneFrameTimeout(byref(self.pData), self.nPayloadSize, stFrameInfo, 1000)
        
        if ret == 0:
            # Success
            width = stFrameInfo.nWidth
            height = stFrameInfo.nHeight
            pixelType = stFrameInfo.enPixelType
            
            logger.info(f"Frame Captured: {width}x{height} | PayloadSize: {self.nPayloadSize} | PixelType: {pixelType}")

            # Check for insane dimensions
            if width > 20000 or height > 20000:
                logger.error(f"Insane dimensions: {width}x{height}. Rejecting.")
                raise Exception(f"Invalid dimensions: {width}x{height}")

            try:
                # 3. Handle data with Color Conversion
                # Use SDK to convert Bayer/Mono to RGB8Packed
                PixelType_Gvsp_RGB8_Packed = 0x02180014 # Constant
                
                nRGBSize = width * height * 3
                # Allocate ctypes buffer for RGB
                pRGBBuf = (ctypes.c_ubyte * nRGBSize)()
                
                stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
                memset(byref(stConvertParam), 0, sizeof(stConvertParam))
                stConvertParam.nWidth = width
                stConvertParam.nHeight = height
                stConvertParam.pSrcData = self.pData
                stConvertParam.nSrcDataLen = self.nPayloadSize
                stConvertParam.enSrcPixelType = pixelType
                stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
                stConvertParam.pDstBuffer = cast(pRGBBuf, POINTER(ctypes.c_ubyte))
                stConvertParam.nDstBufferSize = nRGBSize
                
                ret_conv = self.handle.MV_CC_ConvertPixelType(stConvertParam)
                
                if ret_conv == 0:
                    # Conversion Success -> Create RGB Image
                    # Disable DecompressionBomb warning globally for this module
                    Image.MAX_IMAGE_PIXELS = None
                    
                    rgb_bytes = ctypes.string_at(pRGBBuf, nRGBSize)
                    img = Image.frombytes('RGB', (width, height), rgb_bytes)
                    
                    # Log once to confirm color works (debug)
                    # logger.info(f"Converted to RGB8. Size: {len(rgb_bytes)}")
                    return img
                
                else:
                    logger.warning(f"Color conversion failed (ret={hex(ret_conv)}), falling back to Mono/Raw")
                    # Fallback to original logic
                    raw_bytes = ctypes.string_at(self.pData, self.nPayloadSize)
                    Image.MAX_IMAGE_PIXELS = None 
                    img = Image.frombytes('L', (width, height), raw_bytes)
                    return img.convert("RGB")
                    
            except Exception as e:
                logger.error(f"Image processing failed: {e}")
                raise e
        else:
             raise Exception(f"GetFrame failed: {ret}")

    # --- Streaming Support ---
    def start_streaming(self, callback):
        """
        Start a background thread to capture and callback low-res preview images.
        callback(camera_id, pil_image)
        """
        if self.streaming:
            return
            
        logger.info(f"Camera {self.camera_id} starting preview stream...")
        self.streaming = True
        self.stream_thread = threading.Thread(target=self._preview_loop, args=(callback,), daemon=True)
        self.stream_thread.start()

    def stop_streaming(self):
        """
        Stop the preview stream and wait for thread to join.
        """
        if not self.streaming:
            return
            
        logger.info(f"Camera {self.camera_id} stopping preview stream...")
        self.streaming = False
        if self.stream_thread:
            self.stream_thread.join(timeout=2.0)
            self.stream_thread = None

    def _preview_loop(self, callback):
        while self.streaming:
            try:
                # Reuse existing grab_image logic 
                # (Ideally we would have a lighter 'grab_frame' without deep copying for preview, 
                #  but for stability let's stick to the working grab_image)
                start_time = time.time()
                
                # We can suppress errors here to avoid spamming logs during preview
                try:
                    img = self.grab_image()
                except Exception:
                    time.sleep(0.5)
                    continue

                if not self.streaming: break

                # Resize for UI efficiency (e.g., 800px width)
                # This is crucial: don't send 20MP images to the UI event loop 5 times a second!
                img.thumbnail((800, 600))
                
                # Callback to update UI
                callback(self.camera_id, img)
                
                # Limit FPS (e.g., Target 5 FPS = 0.2s)
                elapsed = time.time() - start_time
                sleep_time = max(0.0, 0.2 - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Preview loop error: {e}")
                time.sleep(1)
