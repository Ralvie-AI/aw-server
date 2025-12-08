import os
import json
import logging 
import platform
import sys

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request
)
from playhouse.shortcuts import model_to_dict

from sd_server.encrypt_image_aes_gcm import encrypt_image_to_json_gcm
from sd_main.sd_desktop.util import (credentials)
from sd_server.utils import get_uuid_address

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    PUBLIC_KEY = os.path.join(os.environ['LOCALAPPDATA'], "Sundial", "Sundial", "sd-server", "public.pem")
elif sys.platform == "darwin":
    PUBLIC_KEY = os.path.join(os.path.expanduser("~"),
                "Library", "Application Support", "Sundial", "sd-server", "public.pem")

blueprint = Blueprint("screenshot", __name__, url_prefix="/screenshot")

@blueprint.route('/', methods=['POST'])
def screenshot():
    logger.info("screen shot testing")
    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    current_app.api.db.get_screenshot_record()

    latest_event = current_app.api.db.get_lastest_event()
    try:
        latest_screenshot = current_app.api.db.get_latest_screenshot()
    except Exception as e:
        latest_screenshot = None 
   
    event_data = model_to_dict(latest_event)

    get_afk_data = json.loads(event_data.get('datastr'))
    file_location = json_data.get('file_location') 
    logger.info(f"file_location => {file_location}")


    # if is_idle_screenshot was false, no need to take screen shot for idle time.
    
    if get_afk_data.get('status') == 'afk' and not json_data.get('is_idle_screenshot'):
        os.remove(file_location)
        return jsonify({
                        'result': "Success",
                        'message': 'Screen capture is disabled when the system is idle.',     
                    }), 200 

    if latest_screenshot:        

        if str(latest_screenshot.event.eventId) == str(event_data.get('eventId')):

            return jsonify({
                        'result': "Conflict",
                        'message': 'Already exists',     
                    }), 409
    
    creds = credentials()
    image_format = "png"
    user_id = creds.get('userId')
    company_id  = creds.get('companyId')
    UUID = get_uuid_address()

    associated_data = f"image_format={image_format},user_id={user_id},company_id={company_id},UUID={UUID}".encode('utf-8')
    encrypted_data_json = encrypt_image_to_json_gcm(file_location, associated_data, public_key_path=PUBLIC_KEY)
    file_path_without_ext, ext = os.path.splitext(file_location)
    json_file = f"{file_path_without_ext}.json"

    try:

        with open(json_file, 'w') as f:
            f.write(encrypted_data_json)
        
        # logger.info(f"Created encrypted JSON file => {json_file}")

        # if os.path.exists(file_location):
        #     os.remove(file_location)
        #     logger.info(f"Removed original PNG after conversion => {file_location}")
            
    except FileNotFoundError as e:
        logger.info(f"Error: File not found at {e}")
    except Exception as e:
        logger.info(f"Error: {e}")
        
    data = {
            "event": str(event_data.get('eventId')),
            "file_path": json_file,
            }
    
    current_app.api.db.save_screenshot(data)     

    return jsonify({
        'result': file_location,
        'message': 'JSON processed successfully',
        'received_data': json_data
    }), 201