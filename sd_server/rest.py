import getpass
import json
from functools import wraps
from threading import Lock
from typing import Dict
from datetime import datetime, timedelta

import iso8601
import jwt
from dateutil.parser import parse
from flask_restx import Api, Resource, fields
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    request,
    send_from_directory,
)
from flask_jwt_extended import  create_access_token, jwt_required
from flask_jwt_extended.exceptions import NoAuthorizationError

from sd_core.util import (
    is_internet_connected, 
    reset_user)
from sd_core.const import (
    SETTINGS_CACHE_KEY, 
    LOGGING_VERBOSE, 
    APPLICATION_CACHE_KEY)
from sd_core import schema, db_cache
from sd_core.models import Event
from sd_core.cache import credentials
from sd_core.os_util import is_windows
from . import logger
from .api import ServerAPI
from .exceptions import BadRequest, Unauthorized

def host_header_check(f):
    """
    Protects against DNS rebinding attacks (see https://github.com/ActivityWatch/activitywatch/security/advisories/GHSA-v9fg-6g9j-h4x4)

    Some discussion in Syncthing how they do it: https://github.com/syncthing/syncthing/issues/4819
    """

    @wraps(f)
    def decorator(*args, **kwargs):
        server_host = current_app.config["HOST"]
        req_host = request.headers.get("host", None)
        if server_host == "0.0.0.0":
            logger.warning(
                "Server is listening on 0.0.0.0, host header check is disabled (potential security issue)."
            )
        elif req_host is None:
            return {"message": "host header is missing"}, 400
        else:
            if req_host.split(":")[0] not in ["localhost", "127.0.0.1", server_host]:
                return {"message": f"host header is invalid (was {req_host})"}, 400
        return f(*args, **kwargs)

    return decorator


authorizations = {
    'Bearer': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
    }
}


blueprint = Blueprint("api", __name__, url_prefix="/api")
api = Api(blueprint, doc="/",
          decorators=[host_header_check], 
          authorizations=authorizations,
          )

@api.errorhandler(NoAuthorizationError)
def handle_no_auth(error):
    return {
        "message": "Authorization token required to execute this endpoint.",
        "error": "unauthorized"
    }, 401


# Loads event and bucket schema from JSONSchema in sd_core
event = api.schema_model("Event", schema.get_json_schema("event"))
bucket = api.schema_model("Bucket", schema.get_json_schema("bucket"))
buckets_export = api.schema_model("Export", schema.get_json_schema("export"))
user = api.schema_model("User", schema.get_json_schema("user"))


# TODO: Construct all the models from JSONSchema?
#       A downside to contructing from JSONSchema: flask-restplus does not have marshalling support

info = api.model(
    "Info",
    {
        "hostname": fields.String(),
        "version": fields.String(),
        "testing": fields.Boolean(),
        "device_id": fields.String(),
    },
)

create_bucket = api.model(
    "CreateBucket",
    {
        "client": fields.String(required=True),
        "type": fields.String(required=True),
        "hostname": fields.String(required=True),
    },
)

update_bucket = api.model(
    "UpdateBucket",
    {
        "client": fields.String(required=False),
        "type": fields.String(required=False),
        "hostname": fields.String(required=False),
        "data": fields.String(required=False),
    },
)

query = api.model(
    "Query",
    {
        "timeperiods": fields.List(
            fields.String, required=True, description="List of periods to query"
        ),
        "query": fields.List(
            fields.String, required=True, description="String list of query statements"
        ),
    },
)


def copy_doc(api_method):
    """
     Copy docstrings from another function to the decorated function. Used to copy docstrings in ServerAPI over to the flask - restplus Resources.

     @param api_method - The method to copy the docstrings from.

     @return A decorator that copies the docstrings from the decorated function
    """
    """Decorator that copies another functions docstring to the decorated function.
    Used to copy the docstrings in ServerAPI over to the flask-restplus Resources.
    (The copied docstrings are then used by flask-restplus/swagger)"""

    def decorator(f):
        """
         Decorate a function to add documentation. This is useful for methods that are decorated with @api_method

         @param f - The function to decorate.

         @return The decorated function as a decorator ( not a decorator
        """
        f.__doc__ = api_method.__doc__
        return f

    return decorator


# Users
@api.route('/0/login')
class Login(Resource):
    @api.expect(user, validate=True)
    def post(self):
        """Authenticate a user and return a JWT access token."""

        data = request.get_json()

        # 1. Fetch the user by email from the Peewee database
        if not current_app.api.check_email(data['email']):
            return {"message": "Invalid email or password"}, 401
        
        # 2. Compare the plain text password with the stored hash
        is_password, user_id = current_app.api.check_password(data['email'], data['password'])
        if is_password:
            # 3. If correct, generate the JWT access token
            access_token = create_access_token(identity=str(user_id))
            return {"token": access_token}, 200
        
        return {"message": "Invalid email or password"}, 401

# Login by ralvie cloud
@api.route("/0/ralvie/login",  doc=False)
class RalvieLoginResource(Resource):
    def post(self):
        """
         Authenticate and log in a user. This is the endpoint for authenticating and log in a user.


         @return A JSON with the result of the authentication and user
        """
        refresh_token = ""
        # Check Internet Connectivity
        # If the internet is not connected return a 200 error message.
        if not is_internet_connected():
            return jsonify({"message": "Please connect to the internet and try again."}), 200

        # Parse Request Data
        data = request.get_json()
        user_name = data.get('userName')
        password = data.get('password')
        companyId = data.get('companyId', None)
        user_id = None

        # JSON response with user_name password user_name user_name password
        if not user_name:
            return jsonify({"message": "User name is mandatory"}), 400
        elif not password:
            return jsonify({"message": "Password is mandatory"}), 400

        # Reset User Data
        reset_user()

        # Authenticate User
        auth_result = current_app.api.authorize(data)        

        # Returns a JSON response with the user credentials.
        if auth_result.status_code == 200 and json.loads(auth_result.text)["code"] == 'UASI0011':
            
            if LOGGING_VERBOSE == 1:
                if companyId:
                    logger.info(f"companyId => {json.loads(auth_result.text)}")
            
            # Retrieve Cached User Credentials
            token = json.loads(auth_result.text)["data"]["access_token"]
            refresh_token = json.loads(auth_result.text)[
                "data"]["refresh_token"]
            # store_credentials(cache_key, SD_KEYS)
            user_id = json.loads(auth_result.text)["data"]["id"]
            current_app.api.get_user_credentials(user_id, 'Bearer ' + token)
            init_db = current_app.api.init_db()

            # Reset the user to the default user
            if not init_db:
                reset_user()
                return {"message": "Can not create the database."}, 500

            current_app.api.create_user(user_name, password)
            # Generate JWT
            user_credentials = credentials()
            payload = {
                "user": getpass.getuser(),
                "email": user_credentials.get("email"),
                "phone": user_credentials.get("phone"),
            }
            encoded_jwt = jwt.encode(payload, user_credentials.get("user_key"),
                                     algorithm="HS256")       

            return {"code": "UASI0011", "message": json.loads(auth_result.text)["message"], "companyId": companyId,
                    "data": {"token": "Bearer " + encoded_jwt, "access_token": "Bearer " + token, "refresh_token": refresh_token}, "userId": user_id}, 200
        else:            
            return {"code": json.loads(auth_result.text)["code"], "message": json.loads(auth_result.text)["message"],
                    "data": json.loads(auth_result.text)["data"], "userId": user_id}, 200


# BUCKETS

@api.route("/0/buckets/<string:bucket_id>/formated_events",  doc=False)
class EventsResource(Resource):
    # For some reason this doesn't work with the JSONSchema variant
    # Marshalling doesn't work with JSONSchema events
    # @api.marshal_list_with(event)
    @api.doc(model=event)
    @api.param("limit", "the maximum number of requests to get")
    @api.param("start", "Start date of events")
    @api.param("end", "End date of events")
    @copy_doc(ServerAPI.get_events)
    def get(self, bucket_id):
        """
         Get events for a bucket. This endpoint is used to retrieve events that have been submitted to the API for a given bucket.

         @param bucket_id - the id of the bucket to retrieve events for

         @return a tuple of ( events status
        """
        args = request.args
        limit = int(args["limit"]) if "limit" in args else -1
        start = iso8601.parse_date(args["start"]) if "start" in args else None
        end = iso8601.parse_date(args["end"]) if "end" in args else None

        events = current_app.api.get_formated_events(
            bucket_id, limit=limit, start=start, end=end
        )
        return events, 200

    # TODO: How to tell expect that it could be a list of events? Until then we can't use validate.
    @api.expect(event)
    @copy_doc(ServerAPI.create_events)
    def post(self, bucket_id):
        """
         Create events in a bucket. This endpoint is used to create one or more events in a bucket.

         @param bucket_id - ID of bucket to create events in

         @return JSON representation of the created event or HTTP status code
        """
        data = request.get_json()
        logger.debug(
            "Received post request for event in bucket '{}' and data: {}".format(
                bucket_id, data
            )
        )

        # Convert a POST data to a list of events.
        if isinstance(data, dict):
            events = [Event(**data)]
        elif isinstance(data, list):
            events = [Event(**e) for e in data]
        else:
            raise BadRequest("Invalid POST data", "")
        event = current_app.api.create_events(bucket_id, events)
        return event.to_json_dict() if event else None, 200


@api.route("/0/buckets/")
class BucketsResource(Resource):
    # TODO: Add response marshalling/validation
    @api.doc(model=bucket)
    @api.doc(security='Bearer')  # Protects this specific endpoint in Swagger
    @jwt_required()    
    @copy_doc(ServerAPI.get_buckets)
    def get(self) -> Dict[str, Dict]:
        """
         Get all buckets. This is a shortcut to : meth : ` ~flask. api. Baskets. get_buckets `.


         @return A dictionary of bucket names and their values keyed by bucket
        """
        return current_app.api.get_buckets()


@api.route("/0/buckets/<string:bucket_id>",  doc=False)
class BucketResource(Resource):
    @api.doc(model=bucket)
    @copy_doc(ServerAPI.get_bucket_metadata)
    def get(self, bucket_id):
        """
         Get metadata for a bucket. This is a GET request to the ` ` S3_bucket_metadata ` ` endpoint.

         @param bucket_id - the ID of the bucket to get metadata for

         @return a dict containing bucket metadata or None if not found
        """
        return current_app.api.get_bucket_metadata(bucket_id)

    @api.expect(create_bucket)
    @copy_doc(ServerAPI.create_bucket)
    def post(self, bucket_id):
        """
         Create a bucket. This endpoint requires authentication and will return a 204 if the bucket was created or a 304 if it already exists.

         @param bucket_id - the id of the bucket to create

         @return http code 200 if bucket was created 304 if it
        """
        data = request.get_json()
        bucket_created = current_app.api.create_bucket(
            bucket_id,
            event_type=data["type"],
            client=data["client"],
            hostname=data["hostname"],
        )
        # Returns a 200 if bucket was created
        if bucket_created:
            return {}, 200
        else:
            return {}, 304

    @api.expect(update_bucket)
    @copy_doc(ServerAPI.update_bucket)
    def put(self, bucket_id):
        """
         Update a bucket. This endpoint is used to update an existing bucket. The request must be made with a JSON object in the body and the data field will be updated to the new data.

         @param bucket_id - the ID of the bucket to update

         @return a 200 response with the updated bucket or an error
        """
        data = request.get_json()
        current_app.api.update_bucket(
            bucket_id,
            event_type=data["type"],
            client=data["client"],
            hostname=data["hostname"],
            data=data["data"],
        )
        return {}, 200

    @copy_doc(ServerAPI.delete_bucket)
    @api.param("force", "Needs to be =1 to delete a bucket it non-testing mode")
    def delete(self, bucket_id):
        """
         Delete a bucket. Only allowed if sd - server is running in testing mode

         @param bucket_id - ID of bucket to delete

         @return 200 if successful 404 if not ( or on error
        """
        args = request.args
        # DeleteBucketUnauthorized if sd server is running in testing mode or if sd server is running in testing mode or if force 1
        if not current_app.api.testing:
            # DeleteBucketUnauthorized if sd server is running in testing mode or if force 1
            if "force" not in args or args["force"] != "1":
                msg = "Deleting buckets is only permitted if sd-server is running in testing mode or if ?force=1"
                raise Unauthorized("DeleteBucketUnauthorized", msg)

        current_app.api.delete_bucket(bucket_id)
        return {}, 200


# EVENTS


@api.route("/0/buckets/<string:bucket_id>/events",  doc=False)
class EventsResource(Resource):
    # For some reason this doesn't work with the JSONSchema variant
    # Marshalling doesn't work with JSONSchema events
    # @api.marshal_list_with(event)
    @api.doc(model=event)
    @api.param("limit", "the maximum number of requests to get")
    @api.param("start", "Start date of events")
    @api.param("end", "End date of events")
    @copy_doc(ServerAPI.get_events)
    def get(self, bucket_id):
        """
         Get events for a bucket. This endpoint is used to retrieve events that have occurred since the last call to : func : ` ~flask. api. Bucket. create `.

         @param bucket_id - the bucket to get events for.

         @return 200 OK with events in JSON. Example request **. : http Example response **. :
        """
        args = request.args
        limit = int(args["limit"]) if "limit" in args else -1
        start = iso8601.parse_date(args["start"]) if "start" in args else None
        end = iso8601.parse_date(args["end"]) if "end" in args else None

        events = current_app.api.get_events(
            bucket_id, limit=limit, start=start, end=end
        )
        return events, 200

    # TODO: How to tell expect that it could be a list of events? Until then we can't use validate.
    @api.expect(event)
    @copy_doc(ServerAPI.create_events)
    def post(self, bucket_id):
        """
         Create events in a bucket. This endpoint is used to create one or more events in a bucket.

         @param bucket_id - ID of bucket to create events in

         @return JSON representation of the created event or HTTP status code
        """
        data = request.get_json()
        logger.debug(
            "Received post request for event in bucket '{}' and data: {}".format(
                bucket_id, data
            )
        )

        # Convert a POST data to a list of events.
        if isinstance(data, dict):
            events = [Event(**data)]
        elif isinstance(data, list):
            events = [Event(**e) for e in data]
        else:
            raise BadRequest("Invalid POST data", "")

        event = current_app.api.create_events(bucket_id, events)
        return event.to_json_dict() if event else None, 200


@api.route("/0/buckets/<string:bucket_id>/events/count")
class EventCountResource(Resource):    
    @api.doc(model=fields.Integer)
    @api.param("start", "Start date of eventcount")
    @api.param("end", "End date of eventcount")
    @copy_doc(ServerAPI.get_eventcount)
    @api.doc(security="Bearer")
    @jwt_required
    def get(self, bucket_id):
        args = request.args
        start = iso8601.parse_date(args["start"]) if "start" in args else None
        end = iso8601.parse_date(args["end"]) if "end" in args else None

        events = current_app.api.get_eventcount(
            bucket_id, start=start, end=end)
        return events, 200


@api.route("/0/buckets/<string:bucket_id>/events/<int:event_id>",  doc=False)
class EventResource(Resource):
    @api.doc(model=event)
    @copy_doc(ServerAPI.get_event)
    def get(self, bucket_id: str, event_id: int):
        """
         Get an event by bucket and event id. This is an endpoint for GET requests that need to be handled by the client.

         @param bucket_id - ID of the bucket containing the event
         @param event_id - ID of the event to retrieve

         @return A tuple of HTTP status code and the event if
        """
        logger.debug(
            f"Received get request for event with id '{event_id}' in bucket '{bucket_id}'"
        )
        event = current_app.api.get_event(bucket_id, event_id)
        # Return event and response code
        if event:
            return event, 200
        else:
            return None, 404

    @copy_doc(ServerAPI.delete_event)
    def delete(self, bucket_id: str, event_id: int):
        """
         Delete an event from a bucket. This is a DELETE request to / api / v1 / bucket_ids

         @param bucket_id - ID of bucket to delete event from
         @param event_id - ID of event to delete from bucket

         @return JSON with " success " as a boolean and " message " as
        """
        logger.debug(
            "Received delete request for event with id '{}' in bucket '{}'".format(
                event_id, bucket_id
            )
        )
        success = current_app.api.delete_event(bucket_id, event_id)
        return {"success": success}, 200

@api.route("/0/buckets/<string:bucket_id>/heartbeat",  doc=False)
class HeartbeatResource(Resource):
    def __init__(self, *args, **kwargs):
        self.lock = Lock()
        super().__init__(*args, **kwargs)

    @api.expect(event, validate=True)
    @api.param("pulsetime", "Largest time window allowed between heartbeats for them to merge")
    @copy_doc(ServerAPI.heartbeat)
    def post(self, bucket_id):
        heartbeat_data = request.get_json()

        if not heartbeat_data['data'].get('title'):
            heartbeat_data['data']['title'] = heartbeat_data['data'].get('app', '')

        if heartbeat_data['data'].get('app') == 'ApplicationFrameHost.exe':
            heartbeat_data['data']['app'] = f"{heartbeat_data['data']['title']}.exe"

        # Retrieve settings
        settings = db_cache.retrieve(SETTINGS_CACHE_KEY)
        if not settings:
            settings = current_app.api.retrieve_all_settings()
            db_cache.store(SETTINGS_CACHE_KEY, settings)

        # Extract the weekdays schedule
        weekdays_schedule = settings.get("weekdays_schedule", {})
        current_time = datetime.now()
        day_name = current_time.strftime("%A").lower()
        schedule = settings.get("schedule", False)

        # Check if the current day is scheduled (True)
        if not weekdays_schedule.get(day_name.capitalize(), False) and schedule:
            print(f"Skipping data capture for {day_name} - not scheduled.")
            return {"message": f"Skipping data capture for {day_name}."}, 200

        # Time range check for scheduling
        start_time_str = weekdays_schedule.get("starttime")
        end_time_str = weekdays_schedule.get("endtime")

        if start_time_str and end_time_str and schedule:
            try:
                time_format = "%H:%M:%S"
                local_start_time = datetime.strptime(f"{current_time.date()} {start_time_str}",
                                                     f"%Y-%m-%d {time_format}")
                local_end_time = datetime.strptime(f"{current_time.date()} {end_time_str}", f"%Y-%m-%d {time_format}")
                print(local_start_time,local_end_time,current_time)

                # Check if the current time is within the scheduled range
                if not (local_start_time <= current_time < local_end_time):
                    print(f"Skipping data capture due to time restriction. Current time: {current_time}, "
                          f"Scheduled start: {local_start_time}, Scheduled end: {local_end_time}.")
                    return {"message": "Skipping data capture due to time restriction."}, 200

            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Error parsing schedule: {e}")
                return {"message": "Schedule parsing error."}, 500

        # Proceed with heartbeat processing
        heartbeat = Event(**heartbeat_data)
        cached_credentials = credentials()

        if cached_credentials is None:
            return {"message": "No cached credentials."}, 400

        try:
            pulsetime = float(request.args.get("pulsetime"))
        except (ValueError, TypeError):
            return {"message": "Missing or invalid required parameter 'pulsetime'"}, 400

        if not self.lock.acquire(timeout=1):
            logger.warning("Heartbeat lock could not be acquired within a reasonable time.")
            return {"message": "Failed to acquire heartbeat lock."}, 500

        try:
            event = current_app.api.heartbeat(bucket_id, heartbeat, pulsetime)
            if event:
                return event.to_json_dict(), 200
            else:
                return {"message": "Heartbeat failed."}, 500
        finally:
            self.lock.release()


# QUERY

# TODO: Perhaps we don't need this, could be done with a query argument to /0/export instead

@api.route("/0/buckets/<string:bucket_id>/export")
class BucketExportResource(Resource):       
    @api.doc(model=buckets_export)
    @api.doc(security="Bearer")
    @jwt_required()
    @copy_doc(ServerAPI.export_bucket)
    def get(self, bucket_id):
        bucket_export = current_app.api.export_bucket(bucket_id)
        payload = {"buckets": {bucket_export["id"]: bucket_export}}
        response = make_response(json.dumps(payload))
        filename = "sd-bucket-export_{}.json".format(bucket_export["id"])
        response.headers["Content-Disposition"] = "attachment; filename={}".format(
            filename
        )
        return response


# LOGGING
@api.route("/0/settings",  doc=False)
class SaveSettings(Resource):
    @copy_doc(ServerAPI.save_settings)
    @api.doc(security="Bearer")
    def post(self):
        """
        Save settings to the database. This is a POST request to /api/v1/settings.

        @return: 200 if successful, 400 if there is an error.
        """
        # Parse JSON data sent in the request body
        data = request.get_json()
        if data:
            # Extract 'code' and 'value' from the parsed JSON
            code = data.get('code')
            value = data.get('value')
            # Check if both 'code' and 'value' are present
            if code is not None and value is not None:
                # Convert value to JSON string
                value_json = value

                # Save settings to the database
                result = current_app.api.save_settings(
                    code=code, value=value_json)

                # Prepare response dictionary
                result_dict = {
                    "id": result.id,  # Assuming id is the primary key of SettingsModel
                    "code": result.code,
                    "value": value_json  # Use the converted value
                }

                return result_dict, 200  # Return the result dictionary with a 200 status code
            else:
                # Handle the case where 'code' or 'value' is missing in the JSON body
                return {"message": "Both 'code' and 'value' must be provided"}, 400
        else:
            # Handle the case where no JSON is provided
            return {"message": "No settings provided"}, 400


@api.route("/0/settings/<string:code>",  doc=False)
class DeleteSettings(Resource):
    @copy_doc(ServerAPI.delete_settings)
    @api.doc(security="Bearer")
    def delete(self, code):
        """
        Delete settings from the database. This is a DELETE request to /api/v1/settings/{code}.

        @param code: The code associated with the settings to be deleted.
        @return: 200 if successful, 404 if settings not found.
        """
        # Delete settings from the database
        # Assuming current_app.api.delete_settings() is your method to delete settings
        result = current_app.api.delete_settings(code=code)
        if result:
            return {"message": "Settings deleted successfully", "code": code}, 200
        else:
            return {"message": f"No settings found with code '{code}'"}, 404


@api.route("/0/getallsettings", doc=False)
class GetAllSettings(Resource):   
    @copy_doc(ServerAPI.retrieve_all_settings)
    def get(self):
        """
        Get settings. This is a GET request to /0/getsettings/{code}.
        """
        settings_dict = db_cache.cache_data(SETTINGS_CACHE_KEY)
        if settings_dict is None:
            db_cache.cache_data(
                SETTINGS_CACHE_KEY, current_app.api.retrieve_all_settings())
            settings_dict = db_cache.cache_data(SETTINGS_CACHE_KEY)

        return settings_dict


@api.route("/0/dashboard/events", doc=False)
class DashboardResource(Resource):
    @api.doc(security="Bearer")
    # @jwt_required()
    def get(self):
        """
        Get dashboard events. GET /api/dashboards/[id]?start=YYYYMMDD&end=YYYYMMDD
        @return 200 on success, 400 if not found, 500 if other
        """
        args = request.args
        start = iso8601.parse_date(
            args.get("start")) if "start" in args else None
        end = iso8601.parse_date(args.get("end")) if "end" in args else None

        # Assuming this function returns a list of blocked events
        blocked_apps = blocked_list()
        events = current_app.api.get_dashboard_events(start=start, end=end)
        if events:
            for i in range(len(events['events']) - 1, -1, -1):
                event = events['events'][i]
                # if "url" in event['data'].keys() and event['data']['url'] and event['data'] ['url'].replace("https://","").replace("http://", "").replace("www.", "") in blocked_apps['url']:
                # print("blocked url",blocked_apps['url'])
                if event['data']['app'] in blocked_apps['app']:
                    del events['events'][i]
                elif removeprotocals(event['url']) in blocked_apps['url']:
                    del events['events'][i]
        return events, 200


@api.route("/0/dashboard/most_used_apps")
class MostUsedAppsResource(Resource):
    @api.doc(security="Bearer")
    @jwt_required()   
    def get(self):
        """
         Get most used apps. This will return a list of apps that have been used in the last 24 hours.


         @return 200 OK if everything worked else 500 Internal Server Error
        """
        args = request.args
        start_time = parse(args["start"])
        end_time = parse(args["end"])
        # start = iso8601.parse_date(start_time) if "start" in args else None
        # end = iso8601.parse_date(end_time) if "end" in args else None

        blocked_apps = blocked_list()
        events = current_app.api.get_most_used_apps(
            start=start_time, end=end_time
        )
        if events:
            for i in range(len(events['most_used_apps']) - 1, -1, -1):
                app_data = events['most_used_apps'][i]
                if "url" in app_data.keys() and app_data['url'] in blocked_apps['url']:
                    del events['most_used_apps'][i]

        return events, 200


@api.route("/0/applicationlist")
class ApplicationListResource(Resource):       
    @copy_doc(ServerAPI.application_list)
    @api.doc(security="Bearer")
    @jwt_required()
    def get(self):
        applications = current_app.api.application_list()
        return applications, 200


@api.route("/0/sync_server",  doc=False)
class SyncServer(Resource):
    def get(self):
        try:
            status = current_app.api.sync_events_to_ralvie()

            app_sync_status = current_app.api.sync_application_to_ralvie()

            print(app_sync_status)

            if status['status'] == "success":
                return {"message": "Data has been synced successfully"}, 200
            elif status['status'] == "Synced_already" or status['status'] == "no_event_ids":
                return {"message": "Data has been synced already"}, 201
            else:
                return {"message": "Data has not been synced"}, 500
        except Exception as e:
            # Log the error and return a 500 status code
            current_app.logger.error(
                "Error occurred during sync_server: %s", e)
            return {"message": "Internal server error"}, 500


# Refresh token
@api.route("/0/ralvie/refresh_token",  doc=False)
class RalvieTokenRefreshResource(Resource):
    def put(self):
        """
         Refresh token. This is the endpoint for refreshing the access token.


         @return A JSON with the result of the authentication and user
        """
        # If the internet is not connected return a 200 error message.
        if not is_internet_connected():
            return jsonify({"message": "Please connect to the internet and try again."}), 200

        data = request.get_json()

        auth_result = current_app.api.refresh_token(data)

        # Returns a JSON response with the user credentials.
        if auth_result.status_code == 200 and json.loads(auth_result.text)["code"] == 'UASI0011':
            token = json.loads(auth_result.text)["data"]["access_token"]
            refresh_token = json.loads(auth_result.text)[
                "data"]["refresh_token"]

            return {"code": "UASI0011", "message": json.loads(auth_result.text)["message"],
                    "data": {"access_token": 'Bearer ' + token, "refresh_token": refresh_token}}, 200
        else:
            return {"code": json.loads(auth_result.text)["code"], "message": json.loads(auth_result.text)["message"],
                    "data": json.loads(auth_result.text)["data"]}, 200


@api.route("/0/server_status")
class server_status(Resource):
    def get(self):
        return 200


def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end
    
def removeprotocals(url):
    parts = url.split('//')
    if len(parts) > 1:
        return parts[1]
    else:
        return url
# EXPORT AND IMPORT


def blocked_list():
    # Initialize the blocked_apps dictionary with empty lists for 'app' and 'url'
    blocked_apps = {"app": [], "url": []}

    # Retrieve application blocking information from the cache
    application_blocked = db_cache.retrieve(APPLICATION_CACHE_KEY)
    if not application_blocked:
        db_cache.store(APPLICATION_CACHE_KEY,
                       current_app.api.application_list())

    if application_blocked:
        # Iterate over each application in the 'app' list
        for app_info in application_blocked.get('app', []):
            # Check if the application is blocked
            if app_info.get('is_blocked', False):
                # If the application is blocked, append its name to the 'app' list in blocked_apps
                app_name = app_info['name']
                if is_windows():
                    app_name += ".exe"  # Append ".exe" for Windows
                blocked_apps['app'].append(app_name)

        # Iterate over each URL entry in the 'url' list
        for url_info in application_blocked.get('url', []):
            # Check if the URL is blocked
            if url_info.get('is_blocked', False):
                # If the URL is blocked, append it to the 'url' list in blocked_apps
                blocked_apps['url'].append(removeprotocals(url_info['url']))

    return blocked_apps