import os
import subprocess
import platform
import re
import hashlib
import json
import logging
import base64

import win32file
import pywintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sd_core.cache import keychain_item_exists, get_password
from sd_server.const import CACHE_KEY

logger = logging.getLogger(__name__)

PIPE_NAME = r'\\.\pipe\AppSocket'


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

def get_system_uuid_from_shell():
    try:
        result = subprocess.run(
            ['powershell', '-Command', '(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID'],
            capture_output=True,
            text=True,
            check=True
        )
        uuid = result.stdout.strip()
        return uuid
    except subprocess.CalledProcessError as e:
        logger.info(f"Error {e}") 
        return None
    
def get_system_uuid():
    system = platform.system()

    if system == "Windows":
        try:
            output = subprocess.check_output(["wmic", "csproduct", "get", "uuid"]).decode()
            lines = output.strip().split("\n")
            uuid = lines[1].strip() if len(lines) > 1 else None
            return uuid
        except FileNotFoundError as e:
            logger.info(f"FileNotFouldError {e}") 
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
        key = email        
        logger.info(f"Getting uuid address from email.")
        return encrypt_system_uuid(system_uuid, key)

    key_item_exists = keychain_item_exists(CACHE_KEY)
    logger.info(f"Getting max address key_item_exists {key_item_exists}")
    if key_item_exists:
        items = get_password(CACHE_KEY)
        if items:
            result = json.loads(items)
            key = result.get('email')
            logger.info(f"Getting email from cache: {key}")
            return encrypt_system_uuid(system_uuid, key)
    return None

def stop_process_by_exe(exe_name):
    logger.info(f"killing start cmd_name {exe_name}")
    subprocess.run(f"taskkill /F /IM {exe_name}", shell=True)
               
if __name__ == '__main__':
    password = "hello@example.com"
    uuid_str = get_system_uuid()
    uuid_str = "5FB99364-A4CD-EE11-2000-316655F2F09C"
    print("uuid_str", uuid_str)
    print("hello world")
    print(get_uuid_address(password, uuid_str))

    # encrypted_token = "gAAAAABokI6y6q2TTBSCFynkAXIkpVGM6JhuVT4IICdoiTDtP3ODJ5eo9e4Inluz3EA6azCYcP8L3F-5TrLjc--Tz5c3c14_lNLvUbKG1iK-YHJWvXsHBvoOjIMwOJq_c77o57YIKGpz"
    # password = "hello@example.com"
    # print("test", decrypt_system_uuid(encrypted_token, password))
    