# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.


DEVELOPMENT_MODE = 1
STAGING = 0
LOGGING_VERBOSE = 0

PROTOCOL = "https"

SYNC_TIME = 600 # 10 minutes

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
# LOCAL_SERVER = 1
# if LOCAL_SERVER == 1:
#     PROTOCOL = "http"
#     # HOST = "localhost:3323"
#     HOST = "182.66.219.114:9010"

##### RESPONSE CODE FROM RALVRCI0000IE SERVER #####
SUCCESSFUL_SYNC_STATUS = "RCI0000" # store the events successful in server side
REJECTED_SYNC_STATUS = "RCE0219" # server rejected these events
NO_USER_FOUND = "RCE0039" # User does not exist
