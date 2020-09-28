#!/usr/bin/env python3
import functools

import jsonschema

from flask import Flask
from flask import Response
from flask import jsonify
from flask import request
from flask_httpauth import HTTPBasicAuth

from service import Service

service = Service()
app = Flask(__name__)
auth = HTTPBasicAuth()


add_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "fields": {
            "type": "object",
            "patternProperties": {
                "^.*$": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "patternProperties": {
                            "^.*$": {"type": "string"}
                        }
                    }
                }
            },
        }
    },
    "required": ["name", "fields"]
}

update_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string"
        },
        "fields": {
            "patternProperties": {
                "^.*$": {
                    "additionalProperties": False,
                    "patternProperties": {
                        "^(([1-9][0-9]*)|0)$": {
                            "patternProperties": {
                                "^.*$": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    },
    "required": [
        "name",
        "fields"
    ]
}


def validate_schema(schema):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                jsonschema.validate(instance=request.json, schema=schema)
            except jsonschema.exceptions.ValidationError:
                success = False
                message = 'Ακατάλληλο σχήμα json.'
                return success, message
            return func(**request.json)
        return wrapper
    return decorator


def make_response(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        success, result_obj = func()
        if isinstance(result_obj, Response):
            return result_obj
        try:
            result = result_obj['message']
            response_code = result_obj['code']
        except (KeyError, TypeError):
            result = result_obj
            response_code = 200
        response = {
            'success': success,
            'result': result
        }
        return jsonify(response), response_code
    return wrapper


@auth.verify_password
def service_site_login(username, password):
    return service.site_login(username, password)


@app.route("/api/public/services")
@make_response
def fetch_all_services():
    all_info = request.args.get('all_info')
    continue_value = request.args.get('continue')
    limit_value = request.args.get('limit')
    kwargs = {}
    if all_info:
        kwargs['fetch_all_info'] = all_info.endswith('rue')
    if continue_value:
        kwargs['continue_value'] = continue_value
    if limit_value:
        kwargs['limit_value'] = limit_value
    return service.fetch_all(**kwargs)


@app.route("/api/public/service")
@make_response
def fetch_service():
    name = request.args.get('name')
    uuid = request.args.get('uuid')
    id_ = request.args.get('id')
    bpmn = request.args.get('bpmn')
    if bpmn == 'digital':
        fetch_bpmn_digital_steps = True
    elif bpmn == 'manual':
        fetch_bpmn_digital_steps = False
    else:
        fetch_bpmn_digital_steps = None
    service_id = uuid or id_
    if name:
        success, result = service.fetch_by_name(
            name, fetch_bpmn_digital_steps=fetch_bpmn_digital_steps)
    elif service_id:
        success, result = service.fetch_by_id(
            id_=service_id,
            id_is_uuid=bool(uuid),
            fetch_bpmn_digital_steps=fetch_bpmn_digital_steps)
    else:
        success, result = False, service.Error.REQUIRED_FETCH_PARAMS
    return success, result


@app.route("/api/public/service/add", methods=['POST'])
@auth.login_required
@make_response
@validate_schema(add_schema)
def add_service(name, fields):
    return service.add(name, fields)


@app.route("/api/public/service/update", methods=['POST'])
@auth.login_required
@make_response
@validate_schema(update_schema)
def update_service(name, fields):
    return service.update(name, fields)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
