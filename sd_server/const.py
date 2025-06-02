# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 1
STAGING = 1

PROTOCOL = "https"

# HOST = 'ralvie.minervaiotstaging.com'

if DEVELOPMENT_MODE == 0:
    HOST = 'ralvie.minervaiotstaging.com'
else:
    if STAGING == 1:
        HOST = 'ralvie.minervaiotstaging.com'
    else:
        HOST = 'me.ralvie.ai'

CACHE_KEY = "Sundial"
