import os
# DEVELOPMENT_MODE = 0 is for local development.
# DEVELOPMENT_MODE = 1 is for production.

DEVELOPMENT_MODE = 0        # no need to change this

DEVELOPMENT_MODE_MACOS = 1

STAGING = 1

PROTOCOL = "https"

PUBLIC_KEY = os.path.join(os.path.expanduser("~"),
                "Library", "Application Support", "Sundial", "sd-server", '{email}-{company_id}-public.pem')

SYNC_TIME = 600 # 10  minutes
SCREEN_SHOT_TIME = 60 # 1  minutes

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'
TMP_VERSION = "1.3.1"
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

LOCAL_SERVER = 0
if LOCAL_SERVER == 1:
    PROTOCOL = "http"
    # HOST = "localhost:3323"
    HOST = "182.66.219.114:9010"


# CONFIG_SERVER = 1

# if CONFIG_SERVER == 1:
#     import os
#     import logging
#     import configparser
#     from sd_core.dirs import get_data_dir
#     file_path = get_data_dir("sd-server")
#     config_file_path = os.path.join(file_path, "server_config.ini")


#     logger = logging.getLogger(__name__)

#     def read_config(name: str):
#         if os.path.isfile(config_file_path):
#             config = configparser.ConfigParser()
#             config.read(config_file_path)
#             try:
#                 return config.get(name, 'protocol'), config.get(name, 'host')
#             except Exception as e:
#                 logger.error(f"Error reading lang for {name}: {e}")
#                 return None, None
#         return None, None
        
#     def write_config(name: str, protocol: str, host: str):
#             config = configparser.ConfigParser()
#             config.read(config_file_path)
#             # Add a section to the config if it doesn t already exist.
#             if not config.has_section(name):
#                 config.add_section(name)

#             config.set(name, 'protocol', protocol)
#             config.set(name, 'host', host)
#             with open(config_file_path, 'w') as configfile:
#                 config.write(configfile)

#     if os.path.exists(config_file_path):
#         PROTOCOL, HOST = read_config("settings")
#         logger.info(f"PROTOCOL => {PROTOCOL}")
#         logger.info(f"HOST => {HOST}")
#     elif not os.path.exists(config_file_path):
#         PROTOCOL = "http"
#         HOST = "182.66.219.114:9010"
#         write_config("settings", PROTOCOL, HOST)

