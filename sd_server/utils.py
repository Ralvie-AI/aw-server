import subprocess
import platform
import re
import base64
import hashlib
import json
import logging

from sd_core.cache import keychain_item_exists, get_password
from sd_core.util import encrypt_uuid, decrypt_uuid
from sd_server.const import CACHE_KEY

logger = logging.getLogger(__name__)

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
    
def generate_fernet_key(password: str) -> bytes:
    key = hashlib.sha256(password.encode()).digest()  # 32-byte key
    return base64.urlsafe_b64encode(key)  # Fernet needs URL-safe base64
    
def uuid_address_encrypt(key):
    text = get_system_uuid()
    return encrypt_uuid(text, key)
    
def uuid_address_decrypt(text, key):
    return decrypt_uuid(text, key)

def get_uuid_address(email=None):

    if email:
        key = email
        fernet_key = generate_fernet_key(key)
        logger.info(f"Getting uuid address from email.")
        return uuid_address_encrypt(fernet_key)

    key_item_exists = keychain_item_exists(CACHE_KEY)
    logger.info(f"Getting max address key_item_exists {key_item_exists}")
    if key_item_exists:
        items = get_password(CACHE_KEY)
        if items:
            result = json.loads(items)
            key = result.get('email')
            fernet_key = generate_fernet_key(key)
            return uuid_address_encrypt(fernet_key)
    return None

if __name__ == '__main__':
    print(get_uuid_address())    
    