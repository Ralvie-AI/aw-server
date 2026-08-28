from pathlib import Path
from datetime import datetime, timedelta, timezone
import ctypes
from pathlib import Path
import ipaddress
import sys
import keyring
import platform
import subprocess
import os
import time
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sd_core.const import TLS_SERVICE_NAME, TLS_DIR, CERT_FILE, KEY_FILE, CERT_FILE_SWIFT
from sd_core.log import setup_logging
import logging
from sd_core.cache import get_password, add_password, keychain_item_exists, delete_password

logger = logging.getLogger(__name__)

def setup_and_save_keychain():
    """
    Create a new Keychain Access and save in Keychain Access
    """
    logger.info('[tls] Setting a new keychain')
    # 1. create key AES-256
    raw_key = AESGCM.generate_key(bit_length=256)
    
    # 2. convert to Hex for save at Keychai
    hex_key = raw_key.hex()
    
    # 3. save at Keychain
    add_password(TLS_SERVICE_NAME, hex_key)


def encrypt(data: bytes, key: bytes) -> bytes:
    nonce = os.urandom(12)

    aesgcm = AESGCM(key)

    ciphertext = aesgcm.encrypt(
        nonce,
        data,
        None,
    )

    return nonce + ciphertext

def decrypt(data: bytes, key: bytes) -> bytes:
    nonce = data[:12]
    ciphertext = data[12:]

    aesgcm = AESGCM(key)

    return aesgcm.decrypt(
        nonce,
        ciphertext,
        None,
    )

def generate():

    setup_logging("tls-generator", log_file=True)
    
    logger.info('[tls] Generate...')

    TLS_DIR.mkdir(parents=True, exist_ok=True)

    #del files for verify
    CERT_FILE.unlink(missing_ok=True)
    CERT_FILE_SWIFT.unlink(missing_ok=True)
    KEY_FILE.unlink(missing_ok=True)

    if keychain_item_exists(TLS_SERVICE_NAME):
        logger.info('[tls] already have PASSWORD - Delete it')
        delete_password(TLS_SERVICE_NAME)
    else:
        logger.info('[tls] Must create new')

    setup_and_save_keychain()


    # Generate RSA private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=3072,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            "localhost",
        ),
    ])

    now = datetime.now(timezone.utc)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(
            x509.random_serial_number()
        )
        .not_valid_before(
            now - timedelta(minutes=1)
        )
        .not_valid_after(
            now + timedelta(days=3650)
        )
        .add_extension(
            x509.BasicConstraints(
                ca=False,
                path_length=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(
                    ipaddress.IPv4Address("127.0.0.1")
                ),
                x509.IPAddress(
                    ipaddress.IPv6Address("::1")
                ),
            ]),
            critical=False,
        )
        .sign(
            key,
            hashes.SHA256(),
        )
    )

    # Serialize private key into PKCS8 PEM
    private_key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Protect the PEM using AESGCM
    protected_key = encrypt(
        private_key_pem,
        bytes.fromhex(get_password(TLS_SERVICE_NAME))
    )

    logger.info('[tls] Writing File...')
    
    # Write certificate
    with open(CERT_FILE, "wb") as f:
        f.write(
            cert.public_bytes(
                serialization.Encoding.PEM
            )
        )

    # Write certificate for .swift use
    with open(CERT_FILE_SWIFT, "wb") as f:
        f.write(
            cert.public_bytes(
                serialization.Encoding.DER
            )
        )

    # Write private key
    with open(KEY_FILE, "wb") as f:
        f.write(protected_key)

    #verify that have complete files
    while not all([CERT_FILE.exists(), KEY_FILE.exists(), CERT_FILE_SWIFT.exists()]):
        logger.info('Incomplete files.')
        logger.info('Creating The new one.')
        generate()
        time.sleep(1)

    return private_key_pem

# ----------------------------------------------------------------------
# Loading the private key
# ----------------------------------------------------------------------

def load_private_key():

    protected_key = KEY_FILE.read_bytes()

    private_key_pem = decrypt(
        protected_key,
        get_password(TLS_SERVICE_NAME)
    )

    return serialization.load_pem_private_key(
        private_key_pem,
        password=None,
    )  

if __name__ == '__main__':
    generate()
