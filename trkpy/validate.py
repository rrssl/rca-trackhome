from jsonschema import validate

HEX_PATTERN = "^0[xX][0-9a-fA-F]+$"
TRACKING_SCHEMA = {
    'type': "object",
    'properties': {
        'anchors': {
            'type': "object",
            'patternProperties': {
                HEX_PATTERN: {
                    'type': "array",
                    'items': {'type': "integer"},
                    'minItems': 3,
                    'maxItems': 3,
                }
            },
            'additionalProperties': False
        },
        'floors': {
            'type': "object",
            'additionalProperties': {
                'type': "array",
                'items': {'type': "string", 'pattern': HEX_PATTERN},
                'minItems': 1,
                'uniqueItems': True
            }
        },
        'tags': {
            'type': "array",
            'items': {'type': "string", 'pattern': HEX_PATTERN},
            'minItems': 1,
            'uniqueItems': True
        },
        'interval': {
            'type': "integer",
            'exclusiveMinimum': 0
        },
    },
    'required': ['anchors', 'tags', 'interval']
}


def validate_tracking_config(conf):
    return validate(conf, TRACKING_SCHEMA)
