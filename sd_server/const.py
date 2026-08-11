import os
from sd_core.const import DEVELOPMENT_MODE, STAGING, CONFIG_SERVER, PUBLIC_KEY, TMP_VERSION, CACHE_KEY, FORCE_VERBOSE

PROTOCOL = "https"

SYNC_TIME = 600 # 10  minutes
SCREEN_SHOT_TIME = 60 # 1  minutes
STATUS_SYNC_TIME = 180 # 3 minutes
STATUS_SYNC_FIRST_TIME = 30 # 30 seconds

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'

TMP_VERSION = "1.3.3"

if STAGING == 1:
    HOST = HOST_DEV
    VERSION_DISPLAY = f"{TMP_VERSION}_beta"
else:
    HOST = HOST_PRO
    VERSION_DISPLAY = f"{TMP_VERSION}"

 ##### RESPONSE CODE FROM RALVIE SERVER #####
SUCCESSFUL_SYNC_STATUS = "RCI0000" # store the events successful in server side
REJECTED_SYNC_STATUS = "RCE0219" # server rejected these events

LOCAL_SERVER = 0
if LOCAL_SERVER == 1:
    PROTOCOL = "http"
    # HOST = "localhost:3323"
    HOST = "182.66.219.114:9010"




