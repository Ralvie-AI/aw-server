import os
import subprocess
import platform
import re
import base64
import hashlib
import json
import logging
import os
import socket
import sys

# import win32file
# import pywintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sd_core.cache import keychain_item_exists, get_password
from sd_server.const import CACHE_KEY, DEVELOPMENT_MODE

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
    system = platform.system()
    logger.info(f"[SEND_GUI] Called with msg: {msg}, system: {system}")

    if system == "Darwin":
        try:
          
            from PySide6.QtNetwork import QLocalSocket
            from PySide6.QtCore import QCoreApplication

            # craete QCoreApplication 
            if QCoreApplication.instance() is None:
                app = QCoreApplication([])

            socket = QLocalSocket()
            socket.connectToServer("AppSocket")

            if not socket.waitForConnected(1000):
                print("[ERROR] Could not connect to AppSocket")
                logger.error("[SEND_GUI] QLocalSocket failed to connect")
                return False

            socket.write(msg.encode())
            socket.flush()
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            logger.info(f"[SEND_GUI] Sent message: {msg}")
            return True

        except Exception as e:
            print(f"[ERROR] Could not send on macOS: {e}")
            logger.exception(f"[SEND_GUI] Failed to send: {e}")
            return False
    else:
        raise NotImplementedError("Unsupported OS")

def get_system_uuid():
    system = platform.system()

    if system == "Windows":
        output = subprocess.check_output(["wmic", "csproduct", "get", "uuid"]).decode()
        lines = output.strip().split("\n")
        return lines[1].strip() if len(lines) > 1 else None

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
        lowercase_password = key.lower()
        if DEVELOPMENT_MODE == 0:
            logger.info(f"mail lowercase {lowercase_password}")
        return encrypt_system_uuid(system_uuid, lowercase_password)

    key_item_exists = keychain_item_exists(CACHE_KEY)
    logger.info(f"Getting max address key_item_exists {key_item_exists}")
    if key_item_exists:
        items = get_password(CACHE_KEY)
        if items:
            result = json.loads(items)
            key = result.get('email')
            lowercase_password = key.lower()
            return encrypt_system_uuid(system_uuid, lowercase_password)
    return None

def stop_process_by_exe(exe_name):
    if DEVELOPMENT_MODE == 0:
        logger.info(f"killing start cmd_name {exe_name}")
    subprocess.run(f"taskkill /F /IM {exe_name}", shell=True)
               
if __name__ == '__main__':
    password = "hello@example.com"
    uuid_str = get_system_uuid()
    uuid_str = "5FB99364-A4CD-EE11-2000-316655F2F09C"
    print("uuid_str", uuid_str)
    print("hello world")
    print(get_uuid_address(password, uuid_str))