import ctypes
from ctypes import wintypes


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


crypt32 = ctypes.WinDLL("crypt32.dll")
kernel32 = ctypes.WinDLL("kernel32.dll")


crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPCWSTR,
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]

crypt32.CryptProtectData.restype = wintypes.BOOL


crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.POINTER(wintypes.LPWSTR),
    ctypes.POINTER(DATA_BLOB),
    wintypes.LPVOID,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]

crypt32.CryptUnprotectData.restype = wintypes.BOOL


kernel32.LocalFree.argtypes = [
    wintypes.HLOCAL,
]

kernel32.LocalFree.restype = wintypes.HLOCAL


def _make_blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)

    blob = DATA_BLOB(
        len(data),
        ctypes.cast(
            buffer,
            ctypes.POINTER(ctypes.c_byte),
        ),
    )

    return blob, buffer


def dpapi_protect(data: bytes) -> bytes:
    input_blob, input_buffer = _make_blob(data)
    output_blob = DATA_BLOB()

    description = "App localhost TLS private key"

    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()

    try:
        return ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )
    finally:
        kernel32.LocalFree(output_blob.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    input_blob, input_buffer = _make_blob(data)
    output_blob = DATA_BLOB()

    description = wintypes.LPWSTR()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()

    try:
        return ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )
    finally:
        if description:
            kernel32.LocalFree(description)

        kernel32.LocalFree(output_blob.pbData)