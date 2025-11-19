# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 0        # no need to change this

DEVELOPMENT_MODE_MACOS = 1

STAGING = 0

PROTOCOL = "https"

SYNC_TIME = 600

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'
TMP_VERSION = "1.1.9"
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



