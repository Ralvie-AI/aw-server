# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 0        # no need to change this

STAGING = 1

PROTOCOL = "https"

SYNC_TIME = 600 # 10  minutes
SCREEN_SHOT_TIME = 300 # 5  minutes

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'
TMP_VERSION = "1.1.8"
if STAGING == 1:
    HOST = HOST_DEV
    VERSION_DISPLAY = f"{TMP_VERSION}_beta"
else:
    HOST = HOST_PRO
    VERSION_DISPLAY = f"{TMP_VERSION}"

CACHE_KEY = "Sundial"

 ##### RESPONSE CODE FROM RALVIE SERVER #####
SUCCESSFUL_SYNC_STATUS = "RCI0000" # store the events successful in server side
REJECTED_SYNC_STATUS = "RCE0219" # server rejected these events

LOCAL_SERVER = 1
if LOCAL_SERVER == 1:
    PROTOCOL = "http"
    # HOST = "localhost:3323"
    HOST = "182.66.219.114:9010"

