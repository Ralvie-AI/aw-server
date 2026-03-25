import json
import base64
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def validate_public_key_file(path):    

    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    begin = "-----BEGIN PUBLIC KEY-----"
    end = "-----END PUBLIC KEY-----"

    if not content.startswith(begin):
        return False

    if end not in content:
        return False

    # Ensure nothing after END
    after = content.split(end)[1].strip()
    if after != "":
        return False

    # Validate base64
    lines = content.splitlines()
    b64_data = "".join(lines[1:-1])
    base64.b64decode(b64_data)

    # Validate crypto key
    serialization.load_pem_public_key(content.encode())

    return True


def load_public_key(filename="public.pem"):
    with open(filename, "rb") as key_file:
        return serialization.load_pem_public_key(key_file.read(), default_backend())
    
# --- Encryption Function (AES-GCM + RSA-OAEP) ---

def encrypt_image_to_json_gcm(image_path,associated_data, public_key_path="public.pem"):
    """
    Encrypts an image file using Hybrid Encryption (AES-GCM + RSA-OAEP) 
    and returns the result in the specified JSON format.
    """
    public_key = load_public_key(public_key_path)

    with open(image_path, "rb") as f:
        plaintext_data = f.read()

    # Generate AES key (256 bits) and Nonce (12 bytes recommended for GCM)
    aes_key = os.urandom(32)
    nonce = os.urandom(12) 
    
    # 1. Encrypt the Image data (Symmetric AES-GCM)
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Supply the associated data to the encryptor
    encryptor.authenticate_additional_data(associated_data)
    
    # GCM does not require padding for the data
    ciphertext = encryptor.update(plaintext_data) + encryptor.finalize()
    
    # Get the authentication tag
    tag = encryptor.tag
    
    # Create the 'ciphertext_with_tag' field
    ciphertext_with_tag = ciphertext + tag

    # 2. Encrypt the AES Key (Asymmetric RSA-OAEP)
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # 3. Format the output as JSON
    encrypted_json = {
        "ciphertext_with_tag": base64.b64encode(ciphertext_with_tag).decode('utf-8'),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "associated_data": base64.b64encode(associated_data).decode('utf-8'),
        "version": "1.0"
    }

    return json.dumps(encrypted_json, indent=4)
