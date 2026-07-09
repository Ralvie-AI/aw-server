import json
import sys
import gc
import base64
import ctypes
from ctypes import wintypes

import requests

# Set up ctypes structures for Windows API
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

# Load the Windows Crypt32 library
crypt32 = ctypes.windll.crypt32

def encrypt_data(plaintext_bytes: bytes) -> bytes:
    """Encrypts bytes using the current Windows user's credentials."""
    if not isinstance(plaintext_bytes, bytes):
        raise TypeError("Data must be bytes.")

    # Populate the input blob
    data_in = DATA_BLOB()
    data_in.cbData = len(plaintext_bytes)
    data_in.pbData = ctypes.cast(ctypes.create_string_buffer(plaintext_bytes), ctypes.POINTER(ctypes.c_byte))

    data_out = DATA_BLOB()

    # Call CryptProtectData
    # 0x01 = CRYPTPROTECT_UI_FORBIDDEN (ensures no Windows UI popup appears)
    success = crypt32.CryptProtectData(
        ctypes.byref(data_in),
        None,  # Optional description string
        None,  # Optional secondary entropy (salt)
        None,  # Reserved
        None,  # Optional prompt structure
        0x01,  # Flags
        ctypes.byref(data_out)
    )

    if not success:
        raise ctypes.WinError()

    # Extract the encrypted bytes from the output blob
    encrypted_result = ctypes.string_at(data_out.pbData, data_out.cbData)
    
    # Free the memory allocated by the OS
    ctypes.windll.kernel32.LocalFree(data_out.pbData)
    
    return encrypted_result

def decrypt_data(ciphertext_bytes: bytes) -> bytearray:
    """Decrypts bytes and returns a mutable bytearray so you can clear it later."""
    if not isinstance(ciphertext_bytes, bytes):
        raise TypeError("Data must be bytes.")

    data_in = DATA_BLOB()
    data_in.cbData = len(ciphertext_bytes)
    data_in.pbData = ctypes.cast(ctypes.create_string_buffer(ciphertext_bytes), ctypes.POINTER(ctypes.c_byte))

    data_out = DATA_BLOB()

    # Call CryptUnprotectData
    success = crypt32.CryptUnprotectData(
        ctypes.byref(data_in),
        None,
        None,
        None,
        None,
        0x01,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(data_out)
    )

    if not success:
        raise ctypes.WinError()

    # Read directly into a mutable bytearray to allow manual memory wiping
    decrypted_result = bytearray(ctypes.string_at(data_out.pbData, data_out.cbData))
    
    # Free OS allocated memory
    ctypes.windll.kernel32.LocalFree(data_out.pbData)
    
    return decrypted_result


def encrypt_dict(data_dict: dict) -> str:
    """Serializes a dictionary to JSON bytes, encrypts it via DPAPI, 

    and returns a portable Base64 string.
    """
    # 1. Convert dict to a UTF-8 encoded json string (bytes)
    json_bytes = json.dumps(data_dict).encode('utf-8')
    
    # 2. Encrypt the raw bytes using DPAPI
    encrypted_bytes = encrypt_data(json_bytes)
    
    # 3. Encode to Base64 so it can be cleanly stored or passed via text/json
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def decrypt_to_dict(encrypted_b64_str: str) -> dict:
    """Decrypts a Base64 DPAPI string back into a Python dictionary, 

    carefully clearing memory strings along the way.
    """
    # 1. Decode Base64 string back to encrypted ciphertext bytes
    ciphertext = base64.b64decode(encrypted_b64_str)
    
    # 2. Decrypt using DPAPI (returns a mutable bytearray)
    decrypted_bytes = decrypt_data(ciphertext)
    
    try:
        # 3. Parse back into a Python dictionary
        decrypted_json_str = decrypted_bytes.decode('utf-8')
        return json.loads(decrypted_json_str)
        
    finally:
        # 4. CRITICAL: Zero out the decrypted bytearray memory buffer immediately
        for i in range(len(decrypted_bytes)):
            decrypted_bytes[i] = 0

def fetch_and_print_keys(url: str, headers: dict):
    try:
        with requests.Session() as session:
            with session.get(url, headers=headers, stream=True, timeout=25) as response:
                response.raise_for_status()

                # Stream to a small in-memory buffer is acceptable here since this process is short-lived
                # But we still avoid full .json()
                chunks = []
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        chunks.append(chunk)

                content = b''.join(chunks)
                data = json.loads(content)

                code = data.get("code")
                credentials_data  = data.get("data", {}).get("credentials", {})
                user_data = data.get("data", {}).get("user", {})

                db_key = credentials_data["dbKey"]
                data_encryption_key = credentials_data["dataEncryptionKey"]
                user_key = credentials_data["userKey"]
                email = user_data.get("email", None)
                phone = user_data.get("phone", None)
                companyId = user_data.get("companyId", None)
                companyName = user_data.get("companyName", None)
                firstName = user_data.get("firstName", None)
                user_id = user_data.get("id", None)

                result = {
                        "db_key": db_key,
                        "data_encryption_key": data_encryption_key,
                        "user_key": user_key,
                        "email": email, 
                        "phone": phone, 
                        "companyId": companyId,
                        "companyName": companyName,
                        "firstName": firstName,
                        "userId": user_id,
                        "code": code,
                        "token": headers.get("Authorization")
                    }                
               
                encrypted_blob = encrypt_dict(result)
                print(encrypted_blob)

                # Cleanup
                del data, credentials_data, content, chunks, user_data
                gc.collect()

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    # Expect URL and headers from command line or stdin
    if len(sys.argv) < 2:
        print(json.dumps({"error": "URL required"}))
        sys.exit(1)

    url = sys.argv[1]
    # You can pass headers as JSON string if needed
    headers = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    fetch_and_print_keys(url, headers)


    # pyinstaller --onefile --noconsole fetch_credentials.py