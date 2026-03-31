import os
import sys
import subprocess
import logging
import time
import threading
from datetime import datetime

import win32file
import pywintypes

from sd_server.const import DEVELOPMENT_MODE, LOGGING_VERBOSE


logger = logging.getLogger(__name__)

PIPE_NAME = r'\\.\pipe\AppSocket'

def send_to_gui(msg: str):
    try:
        handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_WRITE,
            0,  # No sharing
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        win32file.WriteFile(handle, msg.encode())
        win32file.CloseHandle(handle)
        return True
    except pywintypes.error as e:
        print(f"[ERROR] Could not send: {e}")
        return False


def stop_process_by_exe(exe_name, time_sleep=0.2):
    if DEVELOPMENT_MODE == LOGGING_VERBOSE:
        logger.info(f"killing start cmd_name {exe_name}")   
    subprocess.run(f"taskkill /F /IM {exe_name}", shell=True)
    time.sleep(time_sleep)  # wait 200ms for process cleanup

def add_end_time(start_time, seconds_to_add):
    from datetime import datetime, timedelta

    # Parse the ISO string
    dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")

    # Add seconds
    new_dt = dt + timedelta(seconds=seconds_to_add)

    # Convert back to ISO8601 with 'Z'
    # end_time = new_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    # Round to nearest second
    rounded_dt = new_dt.replace(microsecond=0)
    if new_dt.microsecond >= 500_000:
        rounded_dt += timedelta(seconds=1)

    # Format as ISO8601 without fractional seconds
    end_time = rounded_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return end_time

def convert_datetime_string(dt_string: str) -> str:
    from dateutil import parser
    from zoneinfo import ZoneInfo

    dt = parser.parse(dt_string)
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_running_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def _task_runner(exec_cmd, timeout_sec):
    logger.info(f"Starting module {exec_cmd}")
    if not isinstance(exec_cmd, list):
        exec_cmd = [exec_cmd]

    logger.debug("Running: {}".format(exec_cmd))

    # Don't display a console window on Windows
    # See: https://github.com/ActivityWatch/activitywatch/issues/212
    startupinfo = None
    if sys.platform in ("win32", "cygwin"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        # Use the 'with' statement to ensure underlying handles are cleaned up even if exceptions occur
        with subprocess.Popen(
                exec_cmd,
                universal_newlines=True,
                startupinfo=startupinfo
        ) as proc:

            try:
                # Block and wait, with a timeout mechanism to prevent the process accumulation
                proc.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                # If the exe hangs, force kill it to prevent processes from piling up!
                logger.error(f"Task execution timed out ({timeout_sec}s)! Force cleaning up...")
                proc.kill()
                proc.wait()
    except Exception as e:
        logger.error(f"Unexpected error occurred while starting the process: {e}")

def start_exe(exec_cmd, timeout_sec=None):
    # logger.info(f"Starting module start exe {exec_cmd}")
    worker_thread = threading.Thread(
        target=_task_runner,
        args=(exec_cmd, timeout_sec),
        daemon=True
    )
    worker_thread.start()
    return worker_thread
 