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