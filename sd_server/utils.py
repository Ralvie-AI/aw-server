import subprocess
import logging
import time
from datetime import datetime

from sd_core.const import DEVELOPMENT_MODE, LOGGING_VERBOSE

logger = logging.getLogger(__name__)


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

def convert_datetime_string_old(dt_string: str) -> str:
    """
    Converts a datetime string from the format 'YYYY-MM-DD HH:MM:SS.ffffff+00:00' 
    to the format 'YYYY-MM-DDT HH:MM:SSZ' (ISO 8601 without fractional seconds, 
    using 'T' separator and 'Z' suffix for UTC).

    Args:
        dt_string: The input datetime string (e.g., '2025-11-03 05:47:23.663000+00:00').

    Returns:
        The converted datetime string (e.g., '2025-11-03T05:47:23Z').
    """
    
    # Define the format of the input string
    INPUT_FORMAT = '%Y-%m-%d %H:%M:%S.%f%z'
    
    # Define the desired output format (T separator, no fractional seconds, Z suffix for UTC)
    OUTPUT_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

    try:
        # Step 1: Parse the input string into a datetime object
        dt_object = datetime.strptime(dt_string, INPUT_FORMAT)
        
        # Step 2: Format the datetime object to the target string format
        formatted_string = dt_object.strftime(OUTPUT_FORMAT)
        
        return formatted_string
    
    except ValueError as e:
        # Handle cases where the input string doesn't match the expected format
        return f"Error: Failed to parse datetime string. Details: {e}"
