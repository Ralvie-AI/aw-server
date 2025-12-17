import os
import json
import logging 

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request
)
from playhouse.shortcuts import model_to_dict

from sd_server.encrypt_image_aes_gcm import encrypt_image_to_json_gcm
from sd_qt.sd_desktop.util import (credentials)
from sd_server.utils import get_uuid_address
from sd_server.const import PUBLIC_KEY

logger = logging.getLogger(__name__)

blueprint = Blueprint("screenshot", __name__, url_prefix="/screenshot")

@blueprint.route('/', methods=['POST'])
def screenshot():
    logger.info("screen shot testing")
    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    latest_event = current_app.api.db.get_lastest_event()   
    event_data = model_to_dict(latest_event)

    get_afk_data = json.loads(event_data.get('datastr'))
    file_location = json_data.get('file_location') 
    logger.info(f"file_location => {file_location}")

    # if is_idle_screenshot was false, no need to take screen shot for idle time.    
    if get_afk_data.get('status') == 'afk' and not json_data.get('is_idle_screenshot'):
        os.remove(file_location)
        return jsonify({
                        'result': "Success",
                        'message': 'It will not take screenshot because Idle Time Screenshot is disabled ',   
                    }), 200 
    
    creds = credentials()
    image_format = "png"
    user_id = creds.get('userId')
    company_id  = creds.get('companyId')
    UUID = get_uuid_address()

    associated_data = f"image_format={image_format},user_id={user_id},company_id={company_id},UUID={UUID}".encode('utf-8')
    public_key_file = PUBLIC_KEY.format(email=creds.get('email'), company_id=company_id)
    encrypted_data_json = encrypt_image_to_json_gcm(file_location, associated_data, public_key_path=public_key_file)
    file_path_without_ext, ext = os.path.splitext(file_location)
    json_file = f"{file_path_without_ext}.json"    

    try:

        with open(json_file, 'w') as f:
            f.write(encrypted_data_json)
        
    except FileNotFoundError as e:
        logger.info(f"Error: File not found at {e}")
    except Exception as e:
        logger.info(f"Error: {e}")

    logger.info(f"json file exists => {os.path.exists(json_file)}")
    if os.path.exists(json_file):
        os.remove(file_location)
        
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
