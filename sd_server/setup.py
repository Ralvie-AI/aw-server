from pathlib import Path
import os

from setuptools import setup, Extension
from Cython.Build import cythonize

BASE = Path(__file__).resolve().parent
os.chdir(BASE)

extensions = [
    Extension("credentials", ["credentials.py"]),
    Extension("config", ["config.py"]),
    Extension("main", ["main.py"]),
    Extension("server", ["server.py"]),
    Extension("rest", ["rest.py"]),
    Extension("const", ["const.py"]),
    Extension("encrypt_image_aes_gcm", ["encrypt_image_aes_gcm.py"]),    
    Extension("settings", ["settings.py"]),
    Extension("screen_shot", ["screen_shot.py"]),
    Extension("api", ["api.py"]),
    Extension("tls", ["tls.py"]),
]


setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",           
        },
        
    )
)
