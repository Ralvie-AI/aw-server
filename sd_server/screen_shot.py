import os
import json
import logging 
from datetime import datetime 

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
    
    event_id = json_data.get('event_id') 
    latest_event = current_app.api.db.get_event_by_id(event_id)   
    event_data = model_to_dict(latest_event)

    get_afk_data = json.loads(event_data.get('datastr'))
    file_location = json_data.get('file_location') 
    created_at = json_data.get('created_at') 
    logger.info(f"file_location => {file_location}")
    logger.info(f"created_at => {created_at}")

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
            "event_id": event_id,
            "file_path": json_file,
            'created_at': datetime.fromisoformat(created_at)
            }
    
    current_app.api.db.save_screenshot(data)     

    return jsonify({
        'result': file_location,
        'message': 'JSON processed successfully',
        'received_data': json_data
    }), 201



@blueprint.route('/get_event_time_range', methods=['POST'])
def get_event_time_range():
    
    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    start_time = json_data.get('start_time') 
    end_time = json_data.get('end_time') 
    events_range = current_app.api.db.get_events_timestamp_range(start_time, end_time)   
    # logger.info(f"events_range => {type(events_range)}")
    # logger.info(f"events_range => {events_range}")

    events = []
    for event in events_range:
        result = {}
        result['id'] = event.id
        result['timestamp'] = event.timestamp
        result['duration'] = float(event.duration) 
        events.append(result)

        # logger.info(f"event = {event}")
        # logger.info(f"event type = {type(event)}")
        # logger.info(f"event time => {event.timestamp}, type => {type({event.timestamp})}")
    logger.info(f"events => {events}")
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
    