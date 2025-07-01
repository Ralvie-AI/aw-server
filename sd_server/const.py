# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

# DEVELOPMENT_MODE = 1

# STAGING = 0

# PROTOCOL = "https"

# if DEVELOPMENT_MODE == 0:
#     HOST = 'ralvie.minervaiotstaging.com'
# else:
#     HOST = 'me.ralvie.ai'

# # HOST = 'ralvie.minervaiotstaging.com'


# CACHE_KEY = "Sundial"


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