
import sys
import os
import threading
import time
import ctypes
from PIL import Image
from hardware.mock_camera import CameraBase
from utils.logger import setup_logger

logger = setup_logger("HikHardware")

# --- SDK IMPORT CHECK ---
# Default installation path for Hikrobot MVS Python SDK
SDK_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
MVS_RUNTIME_PATH_64 = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
MVS_RUNTIME_PATH_32 = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win32_i86"

def _prepare_mvs_runtime_paths():
    runtime_path = MVS_RUNTIME_PATH_64 if sys.maxsize > 2**32 else MVS_RUNTIME_PATH_32
    if os.path.isdir(runtime_path):
        # Ensure ctypes WinDLL can resolve MvCameraControl.dll and its dependencies.
        os.environ["PATH"] = runtime_path + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(runtime_path)
            except Exception as e:
                logger.warning(f"add_dll_directory failed: {e}")
    else:
        logger.warning(f"MVS runtime path not found: {runtime_path}")

try:
    _prepare_mvs_runtime_paths()
    sys.path.append(SDK_PATH)
    from MvCameraControl_class import *
    HIK_SDK_AVAILABLE = True
except Exception as e:
    HIK_SDK_AVAILABLE = False
    logger.warning(f"Hikvision SDK unavailable at startup: {e}")
    logger.warning(f"Please verify MVS installation path: {SDK_PATH}")

import config

_mvs_sdk_initialized = False


def _ensure_mvs_sdk():
    """程序內首次使用 MVS 前初始化（列舉／連線共用邏輯可呼叫）。"""
    global _mvs_sdk_initialized
    if not HIK_SDK_AVAILABLE or _mvs_sdk_initialized:
        return 0
    ret = MvCamera.MV_CC_Initialize()
    _mvs_sdk_initialized = True
    if ret != 0:
        logger.warning(f"MV_CC_Initialize ret={ret}")
    return ret


def _prepare_gige_enumeration():
    """初始化 SDK 並延長 GigE 列舉逾時（掃描與 connect 列舉前共用）。"""
    _ensure_mvs_sdk()
    try:
        tmo_ret = MvCamera().MV_GIGE_SetEnumDevTimeout(1200)
        if tmo_ret != 0:
            logger.warning(f"MV_GIGE_SetEnumDevTimeout ret={tmo_ret}")
    except Exception as e:
        logger.warning(f"MV_GIGE_SetEnumDevTimeout skipped: {e}")


def _gige_transport_layer_mask():
    """Enum mask: standard GigE + GenTL GigE (自研網卡路徑)；USB 一併請求以免 SDK 行為差異。"""
    return MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_GIGE_DEVICE


def _is_gige_layer(n_tlayer_type):
    return n_tlayer_type in (MV_GIGE_DEVICE, MV_GENTL_GIGE_DEVICE)


def enumerate_gige_camera_ips():
    """
    列舉目前系統上的 GigE 相機「目前 IP」（與 MVS 列舉順序相近），不開啟裝置。
    含標準 GigE 與 GenTL GigE（MV_GENTL_GIGE_DEVICE）；不含純 USB。
    列舉前會延長 GigE discovery 逾時，減少多台時漏掃。
    若 MVS SDK 不可用則回傳空列表。
    """
    if not HIK_SDK_AVAILABLE:
        logger.warning("enumerate_gige_camera_ips: MVS SDK not available.")
        return []
    try:
        _prepare_gige_enumeration()

        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayer_type = _gige_transport_layer_mask()
        ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
        if ret != 0:
            logger.warning(f"enumerate_gige_camera_ips: EnumDevices failed ret={ret}")
            return []
        ips = []
        for i in range(device_list.nDeviceNum):
            mvcc_dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if not _is_gige_layer(mvcc_dev_info.nTLayerType):
                continue
            gige_info = mvcc_dev_info.SpecialInfo.stGigEInfo
            ip_raw = int(gige_info.nCurrentIp)
            current_ip = f"{(ip_raw >> 24) & 0xFF}.{(ip_raw >> 16) & 0xFF}.{(ip_raw >> 8) & 0xFF}.{ip_raw & 0xFF}"
            ips.append(current_ip)
        logger.info(f"enumerate_gige_camera_ips: found {len(ips)} GigE camera(s).")
        return ips
    except Exception as e:
        logger.warning(f"enumerate_gige_camera_ips: {e}")
        return []


class HikCamera(CameraBase):
    def __init__(self, camera_id, ip_address):
        self.camera_id = camera_id
        self.ip_address = ip_address
        self.handle = None
        self.connected = False
        self.capture_lock = threading.Lock()
        
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
        _prepare_gige_enumeration()

        def _gige_current_ip(mvcc_dev_info):
            gige_info = mvcc_dev_info.SpecialInfo.stGigEInfo
            ip_raw = int(gige_info.nCurrentIp)
            return f"{(ip_raw >> 24) & 0xFF}.{(ip_raw >> 16) & 0xFF}.{(ip_raw >> 8) & 0xFF}.{ip_raw & 0xFF}"

        def _ip_is_configured(ip):
            s = (ip or "").strip()
            return bool(s) and s != "0.0.0.0"

        # 1. Enum Devices（與 enumerate_gige_camera_ips 相同遮罩，含 GenTL GigE）
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = _gige_transport_layer_mask()
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            logger.error(f"Enum Devices failed: {ret}")
            return False

        # GigE-only list (USB etc. in the same enum must not consume fallback slot indices)
        gige_list = []
        for i in range(deviceList.nDeviceNum):
            mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if _is_gige_layer(mvcc_dev_info.nTLayerType):
                gige_list.append(mvcc_dev_info)

        # 2. Match by configured IP, else fallback: camera_id N -> GigE list index N-1
        target_device_info = None
        want_ip = _ip_is_configured(self.ip_address)
        cfg_ip = (self.ip_address or "").strip() if want_ip else ""

        if want_ip:
            for mvcc_dev_info in gige_list:
                current_ip = _gige_current_ip(mvcc_dev_info)
                if current_ip == cfg_ip:
                    target_device_info = mvcc_dev_info
                    logger.info(f"Camera {self.camera_id} matched by IP: {current_ip}")
                    break

        if target_device_info is None:
            idx = self.camera_id - 1
            if 0 <= idx < len(gige_list):
                target_device_info = gige_list[idx]
                logger.warning(
                    f"Camera {self.camera_id} IP {self.ip_address!r} unset or no match; "
                    f"using GigE-only order fallback (index {idx} of {len(gige_list)})."
                )
            else:
                logger.error(
                    f"Camera {self.camera_id} not found: {len(gige_list)} GigE device(s) enumerated, "
                    f"need index {idx}."
                )
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

    def grab_image(self, blocking=True):
        if blocking:
            with self.capture_lock:
                return self._grab_image_unlocked()

        if not self.capture_lock.acquire(blocking=False):
            raise Exception(f"HikCamera {self.camera_id} is busy")
        try:
            return self._grab_image_unlocked()
        finally:
            self.capture_lock.release()

    def _grab_image_unlocked(self):
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
        
        timeout_ms = max(200, min(int(config.GRAB_FRAME_TIMEOUT_MS), 60000))
        ret = self.handle.MV_CC_GetOneFrameTimeout(
            byref(self.pData), self.nPayloadSize, stFrameInfo, timeout_ms
        )
        
        if ret == 0:
            # Success
            width = stFrameInfo.nWidth
            height = stFrameInfo.nHeight
            pixelType = stFrameInfo.enPixelType
            
            logger.debug(f"Frame Captured: {width}x{height} | PayloadSize: {self.nPayloadSize} | PixelType: {pixelType}")

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
                
                # Preview must not contend with operator-triggered capture.
                # If capture is busy, skip this preview frame instead of queueing behind it.
                try:
                    img = self.grab_image(blocking=False)
                except Exception:
                    time.sleep(0.05)
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
