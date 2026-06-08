import os 

from sd_core.const import DEVELOPMENT_MODE, STAGING, CONFIG_SERVER
from sd_server.version import GIT_COMMIT

PROTOCOL = "https"

HOST_DEV = 'ralvie.minervaiotstaging.com'
HOST_PRO = 'me.ralvie.ai'


GITHUB_COMMIT_ID=f"main/windows_{GIT_COMMIT}"

if DEVELOPMENT_MODE == 0:
    if STAGING == 1:
        REMOTE_HOST = HOST_DEV
    else:
        REMOTE_HOST = HOST_PRO
else:
    if STAGING == 1:
        REMOTE_HOST = HOST_DEV
    else:
        REMOTE_HOST = HOST_PRO


##### RESPONSE CODE FROM RALVRCI0000IE SERVER #####
SUCCESSFUL_SYNC_STATUS = "RCI0000" # store the events successful in server side
REJECTED_SYNC_STATUS = "RCE0219" # server rejected these events
NO_USER_FOUND = "RCE0039" # User does not exist

if CONFIG_SERVER == 1:
    import logging    
    from sd_core.dirs import get_data_dir
    from sd_core.util import read_config, write_config
    file_path = get_data_dir("sd-server")
    config_file_path = os.path.join(file_path, "server_config.ini")
    logger = logging.getLogger(__name__)    

    if os.path.exists(config_file_path):
        PROTOCOL, REMOTE_HOST = read_config(config_file_path, "settings")
        logger.info(f"PROTOCOL => {PROTOCOL}")
        logger.info(f"HOST => {REMOTE_HOST}")
    elif not os.path.exists(config_file_path):
        PROTOCOL = "http"
        REMOTE_HOST = "182.66.219.114:9010"
        # PROTOCOL = "https"
        # HOST = "ralvie.minervaiotstaging.com"
        write_config(config_file_path, "settings", PROTOCOL, REMOTE_HOST)
