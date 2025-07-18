import subprocess
import platform
import re
import base64
import hashlib
import json
import logging

import win32file
import pywintypes
from cryptography.fernet import Fernet, InvalidToken

from sd_core.cache import keychain_item_exists, get_password
from sd_server.const import CACHE_KEY

logger = logging.getLogger(__name__)

PIPE_NAME = r'\\.\pipe\AppSocket'

def decrypt_system_uuid(encrypted_token, password):
    """
    Decrypt a Fernet token to retrieve the original UUID.

    @param encrypted_token - Base64-encoded Fernet token (as produced by encrypt_uuid).
    @param password - Password used to derive the Fernet key for decryption.
    @return Decrypted UUID as a string, or None if decryption fails.
    """
    try:
        # Derive 32-byte key from SHA-256 and base64-url encode it
        hashed = hashlib.sha256(password.encode('utf-8')).digest()
        base64_key = base64.urlsafe_b64encode(hashed).decode('utf-8')
        fernet = Fernet(base64_key)
        
        # Decrypt the Fernet token
        decrypted_bytes = fernet.decrypt(encrypted_token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')  # Return UUID as string
    except InvalidToken as e:
        print(f"decrypt_system_uuid error: Invalid token or key: {e}")
        return None
    except Exception as e:
        print(f"decrypt_system_uuid error: {e}")
        return None

def encrypt_system_uuid(uuid_str, password):
    """
    Encrypt UUID and return it as Base64 encoded string. This is useful for storing UUIDs in DB.

    @param uuid_str - UUID to be encrypted.
    @param password - Password to derive Fernet key for encryption. Must be able to decrypt UUIDs.
    @return Base64 encoded UUID or None if encryption failed for any reason.
    """
    try:
        # Derive 32-byte key from SHA-256 and base64-url encode it
        hashed = hashlib.sha256(password.encode('utf-8')).digest()
        base64_key = base64.urlsafe_b64encode(hashed).decode('utf-8')
        fernet = Fernet(base64_key)
        encrypted_uuid = fernet.encrypt(str(uuid_str).encode('utf-8'))
        return encrypted_uuid.decode('utf-8')  # Return Fernet token directly
    except Exception as e:
        print(f"encrypt_uuid error: {e}")
        return None

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
    
def get_uuid_address(email=None):

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
            return encrypt_system_uuid(system_uuid, key)
    return None

if __name__ == '__main__':
    password = "hello@example.com"
    uuid_str = get_system_uuid()
    print("uuid_str", uuid_str)
    print("hello world")
    print(get_uuid_address(password))
