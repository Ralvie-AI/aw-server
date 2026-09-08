import os
import json
import logging 
from datetime import datetime 

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    abort,
)
import psutil
from playhouse.shortcuts import model_to_dict

from sd_core.const import PUBLIC_KEY
from sd_core.cache import credentials
from sd_core.system_uuid import get_uuid_address
from sd_server.encrypt_image_aes_gcm import encrypt_image_to_json_gcm, validate_public_key_file


ALLOWED_PROCESSES = {
    "sd-pixel-engine.exe",
    "sd-ocr-activity.exe",
    "sd-ocr-event.exe",
}


def is_request_from_allowed_process():
    
    if request.remote_addr not in ('127.0.0.1', 'localhost'):
        return False
        
    client_port = request.environ.get('REMOTE_PORT')
    if not client_port:
        return False
        
    client_port = int(client_port)


    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == client_port:
            try:
                process = psutil.Process(conn.pid)
                process_name = process.name().lower()
                
                # Check if the process name is in our allowed list
                if process_name in ALLOWED_PROCESSES:
                    print(f"[ACCESS GRANTED] Verified request from: {process_name} (PID: {conn.pid})")
                    return True
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
    return False


logger = logging.getLogger(__name__)

blueprint = Blueprint("screenshot", __name__, url_prefix="/screenshot")

@blueprint.route('/', methods=['POST'])
def screenshot():

    if not is_request_from_allowed_process():
        abort(403, description="Forbidden: Request must originate from sd-pixel-engine.exe")

    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    event_id = json_data.get('event_id') 
    latest_event = current_app.api.db.get_event_by_id(event_id)   
    is_ocr_text_enabled = json_data.get('is_ocr_text_enabled')    
    event_data = model_to_dict(latest_event)

    get_afk_data = json.loads(event_data.get('datastr'))
    file_location = json_data.get('file_location') 
    created_at = json_data.get('created_at') 

    # if is_idle_screenshot was false, no need to take screen shot for idle time.    
    if get_afk_data.get('status') == 'afk' and not json_data.get('is_idle_screenshot'):
        file_root, ext = os.path.splitext(file_location)
        ocr_file = file_root + "_ocr.png"

        logger.info(f"Deleting full screenshot => {file_location}")
        logger.info(f"Deleteing ocr file => {ocr_file}")

        os.remove(file_location)
        os.remove(ocr_file)
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

    if os.path.exists(public_key_file) and validate_public_key_file(public_key_file):

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
        
        data = {
                "event_id": event_id,
                "file_path": json_file,
                'created_at': datetime.fromisoformat(created_at),
                'is_ocr_text_enabled': is_ocr_text_enabled,
                }
        
        current_app.api.db.save_screenshot(data)     

        return jsonify({
            'result': file_location,
            'message': 'JSON processed successfully',
            'received_data': json_data
        }), 201

    else:
        logger.info(f"No public key found {public_key_file}")
        data = {
                "event_id": event_id,
                "file_path": file_location,
                'created_at': datetime.fromisoformat(created_at),
                'is_ocr_text_enabled': is_ocr_text_enabled,
                }
        
        current_app.api.db.save_screenshot(data)     

        return jsonify({
            'result': file_location,
            'message': 'JSON processed successfully',
            'received_data': json_data
        }), 201

@blueprint.route('/get_event_time_range', methods=['POST'])
def get_event_time_range():

    if not is_request_from_allowed_process():
        abort(403, description="Forbidden: Request must originate from sd-pixel-engine.exe")
    
    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    start_time = json_data.get('start_time') 
    end_time = json_data.get('end_time') 
    events_range = current_app.api.db.get_events_timestamp_range(start_time, end_time)   

    events = []
    for event in events_range:
        result = {}
        result['id'] = event.id
        result['timestamp'] = event.timestamp
        result['duration'] = float(event.duration) 
        events.append(result)

    if events:
        return jsonify({
            'result': json.dumps(events),
            'event_id': "",
            'message': 'JSON processed successfully',        
        }), 200
    else:
        latest_event = current_app.api.db.get_lastest_event()   
        event_data = model_to_dict(latest_event)

        return jsonify({
            'result': json.dumps(events),
            'event_id': event_data.get('id'),
            'message': 'JSON processed successfully',        
        }), 200


@blueprint.route('/update_ocr_text', methods=['POST'])
def update_ocr_text():

    if not is_request_from_allowed_process():
        abort(403, description="Forbidden: Request must originate from sd-ocr-activity.exe")
    
    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    screenshot_id = json_data.get('screenshot_id') 
    ocr_result = json_data.get('ocr_text') 
    current_app.api.db.update_ocr_text(screenshot_id, ocr_result)
    
    return jsonify({        
        'message': 'JSON processed successfully',        
    }), 200


@blueprint.route('/event/screenshots', methods=['POST'])
def create_event_screenshot():

    if not is_request_from_allowed_process():
        abort(403, description="Forbidden: Request must originate from sd-ocr-event.exe")

    json_data = request.get_json()  # Expects Content-Type: application/json
    logger.info(f"json_data => {json_data}")
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    event_id = json_data.get('event_id')
    is_ocr_text_enabled = json_data.get('is_ocr_text_enabled')
    is_event_screenshot = json_data.get('is_event_screenshot')
    file_location = json_data.get('file_location')
    created_at = json_data.get('created_at') 

    data = {
    "event_id": event_id,
    "file_path": file_location,
    'created_at': datetime.fromisoformat(created_at),
    'is_ocr_text_enabled': is_ocr_text_enabled,
    'is_event_screenshot': is_event_screenshot,
    }
            
    screenshot_id = current_app.api.db.save_event_screenshot(data)

    return jsonify({
        'result': file_location,
        'message': 'JSON processed successfully',
        'received_data': json_data,
        'screenshot_id': screenshot_id
    }), 201
