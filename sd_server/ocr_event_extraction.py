import json
import logging 

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request
)

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

    if screenshot_path == 'Screen is locked.':
        data = {
            "event_id": event_id,
            "ocr_text": json.dumps({"data": [{"text": "Screen is locked."}]}),
            "created_at": screenshot_time,
            "is_event_screenshot": 1
        }    
    else:
        data = {
            "event_id": event_id,
            "file_path": screenshot_path,
            "created_at": screenshot_time,
            "is_event_screenshot": 1
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

@blueprint.route('/schedule/settings', methods=['GET'])
def get_schedule_settings():

    # Retrieve the weekday schedule configured by the user in Sundial from the database
    weekdays_schedule = current_app.api.get_settings('weekdays_schedule')

    # Define the time and datetime formats
    time_format = '%H:%M:%S'
    date_format = '%y-%m-%d %H:%M:%S'

    # Get the current UTC datetime and the full weekday name
    dt = datetime.now(timezone.utc)
    current_dt = dt.strftime(date_format)
    current_day_name = dt.strftime('%A')

    # Convert the datetime retrieved from the database to UTC
    start_time = (
        datetime.strptime(weekdays_schedule['starttime'], time_format)
        .replace(year=dt.year, month=dt.month, day=dt.day)
        .astimezone(tz=ZoneInfo('utc'))
        .strftime(date_format)
    )
    end_time = (
        datetime.strptime(weekdays_schedule['endtime'], time_format)
        .replace(year=dt.year, month=dt.month, day=dt.day)
        .astimezone(tz=ZoneInfo('utc'))
        .strftime(date_format)
    )

    # Update the start and end times in weekdays_schedule without modifying the database
    weekdays_schedule['starttime'] = start_time
    weekdays_schedule['endtime'] = end_time

    # validation
        # is_active_day => Check whether today is a scheduled working day
        # is_active_time_interval => Check whether the current time falls within the scheduled time interval
    is_active_day = weekdays_schedule[current_day_name]
    is_active_time_interval = (
        True 
        if (
            (datetime.strptime(end_time, date_format) > datetime.strptime(current_dt, date_format)) 
            and 
            (datetime.strptime(start_time, date_format) < datetime.strptime(current_dt, date_format))
        )
        else False
    )

    is_active_schedule = all([is_active_day, is_active_time_interval])

    return {"is_active_schedule": is_active_schedule}, 200
