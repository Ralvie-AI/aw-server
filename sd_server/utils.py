import os
import subprocess
import platform
import re
import hashlib
import json
import logging
import base64
import time
from datetime import datetime

import win32file
import pywintypes
import win32com.client
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from mss import mss

from sd_core.cache import keychain_item_exists, get_password
from sd_server.const import CACHE_KEY

logger = logging.getLogger(__name__)

PIPE_NAME = r'\\.\pipe\AppSocket'


# Generate uuid if WMIC and PowerShell are not available
def generate_uuid():
    import ctypes
    import hashlib
    import uuid
    import socket
    import winreg

    def get_machine_guid():
        """Get Windows MachineGuid from registry"""
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography")
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return value
        except Exception:
            return None

    def get_volume_serial(drive="C:\\"):
        """Get C: drive volume serial using Windows API"""
        try:
            serial_number = ctypes.c_uint(0)
            max_component_length = ctypes.c_uint(0)
            file_system_flags = ctypes.c_uint(0)
            ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive),
                None,
                0,
                ctypes.byref(serial_number),
                ctypes.byref(max_component_length),
                ctypes.byref(file_system_flags),
                None,
                0
            )
            return f"{serial_number.value:08X}"
        except Exception:
            return None

    def get_hostname():
        """Get hostname"""
        try:
            return socket.gethostname()
        except:
            return None

    def generate_machine_uuid():
        """Generate a deterministic machine UUID that ignores MAC addresses"""
        parts = []

        mguid = get_machine_guid()
        if mguid:
            parts.append(mguid)

        hostname = get_hostname()
        if hostname:
            parts.append(hostname)

        vol = get_volume_serial()
        if vol:
            parts.append(vol)

        if not parts:
            # fallback to random UUID
            parts.append(str(uuid.uuid4()))

        # Combine parts and hash
        raw = "|".join(parts).encode("utf-8")
        hash_bytes = hashlib.sha256(raw).digest()

        # Use first 16 bytes to create UUID
        machine_uuid = uuid.UUID(bytes=hash_bytes[:16])
        return str(machine_uuid).upper()
    
    return generate_machine_uuid()


def derive_key(email: str) -> bytes:
    # SHA-256 gives 32 bytes suitable for AES-256
    return hashlib.sha256(email.encode()).digest()

def encrypt_system_uuid(system_uuid: str, email: str) -> str:
    key = derive_key(email)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce recommended for AESGCM
    encrypted = aesgcm.encrypt(nonce, system_uuid.encode(), None)
    token = nonce + encrypted  # prepend nonce for later use
    return base64.urlsafe_b64encode(token).decode()

def decrypt_system_uuid(token: str, email: str) -> str:
    key = derive_key(email)
    data = base64.urlsafe_b64decode(token)
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    decrypted = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted.decode()

def send_to_gui(msg: str):
    try:
        handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_WRITE,
            0,  # No sharing
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        win32file.WriteFile(handle, msg.encode())
        win32file.CloseHandle(handle)
        return True
    except pywintypes.error as e:
        print(f"[ERROR] Could not send: {e}")
        return False

def get_system_uuid_from_win32com_client():

    logger.info("Get UUID from get_system_uuid_from_win32com_client")
    try:
        wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")
        item_uuid = None
        for item in wmi.ExecQuery("SELECT * FROM Win32_ComputerSystemProduct"):
            item_uuid = item.UUID
            logger.info(f"Vendor: {item.Vendor}") 
            logger.info(f"Name: {item.Name}") 
            logger.info(f"IdentifyingNumber: {item.IdentifyingNumber}") 
        return item_uuid
    except Exception as e:
        logger.info(f"get_system_uuid_from_win32com_client: {str(e)}")
        logger.info(f"Get UUID from generate_uuid")
        return generate_uuid()

def get_system_uuid_from_shell():
    try:
        result = subprocess.run(
            ['powershell', '-Command', '(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID'],
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        uuid = result.stdout.strip()
        return uuid
    except subprocess.CalledProcessError as e:
        logger.info(f"Error {e}") 
        return None
    except FileNotFoundError as e:
        logger.info(f"FileNotFoundError {e}") 
        logger.info(f"Getting uuid address from win32com client.")
        return get_system_uuid_from_win32com_client()
        
    
def get_system_uuid():
    system = platform.system()

    if system == "Windows":
        try:
            output = subprocess.check_output(["wmic", "csproduct", "get", "uuid"],
                                             creationflags=subprocess.CREATE_NO_WINDOW,
                                             ).decode()
            lines = output.strip().split("\n")
            uuid = lines[1].strip() if len(lines) > 1 else None
            return uuid
        except FileNotFoundError as e:
            logger.info(f"FileNotFoundError {e}") 
            logger.info(f"Getting uuid address from power shell.")
            return get_system_uuid_from_shell()
        except Exception as e:
            logger.info(f"Exception {e}")            
            return None 

    elif system == "Darwin":  # macOS
        output = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
        ).decode()
        match = re.search(r'"IOPlatformUUID" = "([^"]+)"', output)
        return match.group(1) if match else None

    else:
        raise NotImplementedError("Unsupported OS")
    
def get_uuid_address(email=None, system_uuid=None):

    if not system_uuid:
        system_uuid = get_system_uuid()

    if email:                
        logger.info(f"Getting uuid address from email.")
        key = email
        lowercase_password = key.lower()
        logger.info(f"mail lowercase {lowercase_password}")
        return encrypt_system_uuid(system_uuid, lowercase_password)

    key_item_exists = keychain_item_exists(CACHE_KEY)
    logger.info(f"Getting max address key_item_exists {key_item_exists}")
    if key_item_exists:
        items = get_password(CACHE_KEY)
        if items:
            result = json.loads(items)
            key = result.get('email')
            logger.info(f"Getting email from cache: {key}")
            lowercase_password = key.lower()
            logger.info(f"mail lowercase {lowercase_password}")
            return encrypt_system_uuid(system_uuid, lowercase_password)
    return None

def stop_process_by_exe(exe_name, time_sleep=0.2):
    logger.info(f"killing start cmd_name {exe_name}")
    subprocess.run(f"taskkill /F /IM {exe_name}", shell=True)
    time.sleep(time_sleep)  # wait 200ms for process cleanup

def convert_datetime_string(dt_string: str) -> str:
    from dateutil import parser
    from zoneinfo import ZoneInfo

    dt = parser.parse(dt_string)
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

def convert_datetime_string_old(dt_string: str) -> str:
    """
    Converts a datetime string from the format 'YYYY-MM-DD HH:MM:SS.ffffff+00:00' 
    to the format 'YYYY-MM-DDT HH:MM:SSZ' (ISO 8601 without fractional seconds, 
    using 'T' separator and 'Z' suffix for UTC).

    Args:
        dt_string: The input datetime string (e.g., '2025-11-03 05:47:23.663000+00:00').

    Returns:
        The converted datetime string (e.g., '2025-11-03T05:47:23Z').
    """
    
    # Define the format of the input string
    INPUT_FORMAT = '%Y-%m-%d %H:%M:%S.%f%z'
    
    # Define the desired output format (T separator, no fractional seconds, Z suffix for UTC)
    OUTPUT_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

    try:
        # Step 1: Parse the input string into a datetime object
        dt_object = datetime.strptime(dt_string, INPUT_FORMAT)
        
        # Step 2: Format the datetime object to the target string format
        formatted_string = dt_object.strftime(OUTPUT_FORMAT)
        
        return formatted_string
    
    except ValueError as e:
        # Handle cases where the input string doesn't match the expected format
        return f"Error: Failed to parse datetime string. Details: {e}"
               
if __name__ == '__main__':

    # password = "hello@example.com"
    password = None
    uuid_str = get_system_uuid()
    # print(uuid_str)
    uuid_str = generate_uuid()
    # uuid_str = "5FB99364-A4CD-EE11-2000-316655F2F09C"
    print("uuid_str", uuid_str)
    # print("hello world")
    encrypted_token = get_uuid_address()
    print("encrypted_token ", encrypted_token)
    # print("test", decrypt_system_uuid(encrypted_token, password))



    # encrypted_token = "gAAAAABokI6y6q2TTBSCFynkAXIkpVGM6JhuVT4IICdoiTDtP3ODJ5eo9e4Inluz3EA6azCYcP8L3F-5TrLjc--Tz5c3c14_lNLvUbKG1iK-YHJWvXsHBvoOjIMwOJq_c77o57YIKGpz"
    # password = "hello@example.com"
    # print("test", decrypt_system_uuid(encrypted_token, password))
    