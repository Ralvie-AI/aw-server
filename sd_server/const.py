# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 1
STAGING = 1

PROTOCOL = "https"

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'

if DEVELOPMENT_MODE == 0:
    if STAGING == 1:
        HOST = HOST_DEV
    else:
        HOST = HOST_PRO
else:
    if STAGING == 1:
        HOST = HOST_DEV
    else:
        HOST = HOST_PRO

CACHE_KEY = "Sundial"


# local server
LOCAL_SERVER = 1
if LOCAL_SERVER == 1:
    PROTOCOL = "http"
    # HOST = "localhost:3323"
    HOST = "14.97.160.178:9010"