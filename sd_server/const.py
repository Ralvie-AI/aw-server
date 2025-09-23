# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 0        # no need to change this

STAGING = 0

PROTOCOL = "https"

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'

if STAGING == 1:
    HOST = HOST_DEV
else:
    HOST = HOST_PRO

CACHE_KEY = "Sundial"

 ##### RESPONSE CODE FROM RALVIE SERVER #####
SUCCESSFUL_SYNC_STATUS = "RCI0000" # store the events successful in server side
REJECTED_SYNC_STATUS = "RCE0219" # server rejected these events
