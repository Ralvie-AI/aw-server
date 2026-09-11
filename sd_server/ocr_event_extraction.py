import json
import logging 

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request
)

logger = logging.getLogger(__name__)

blueprint = Blueprint("ocr_event", __name__, url_prefix="/ocr_event")

@blueprint.route('/', methods=['POST'])
def ocr_event():

    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400
    
    event_id = json_data.get('event_id')
    screenshot_path = json_data.get('screenshot_path')
    screenshot_time = json_data.get('screenshot_time')

    logger.debug(f'event_id: {event_id}, screenshot_path: {screenshot_path}, screenshot_time: {screenshot_time}')
    

    data = {
        "event_id": event_id,
        "file_path": screenshot_path,
        "created_at": screenshot_time,
        "s_event": 1
    }

    current_app.api.db.save_screenshot(data)

    return jsonify({
        'result': json.dumps(data),
        'message': 'JSON processed successfully',
        'received_data': json_data
    }), 201
    
@blueprint.route('/ocr_event_extraction', methods=['POST'])
def ocr_event_extraction():

    json_data = request.get_json()  # Expects Content-Type: application/json
    if not json_data:
        return jsonify({'error': 'No JSON payload provided'}), 400

    event_id = json_data.get('event_id')
    ocr_text = json_data.get('ocr_text')

    logger.debug(f'event_id: {event_id}, ocr_text: {ocr_text}')
    
    if ocr_text == 'null':
        return jsonify({
            'result': 'ocr_text is NONE',
            'message': 'JSON processed successfully',
            'received_data': json_data
        }), 200

    else:  

        current_app.api.db.update_ocr_event_text(event_id, ocr_text)

        return jsonify({
            'result': "saved",
            'message': 'JSON processed successfully',
            'received_data': json_data
        }), 201