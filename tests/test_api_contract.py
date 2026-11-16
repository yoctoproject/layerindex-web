# layerindex-web - tests for the shape of the REST API responses
#
# Copyright (C) 2026 Qbee AS
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-Generated: written with Claude Code

# BitBake's layer index client, Toaster and other tools read these responses
# and released versions of them cannot be changed, so tests/data/api_schema.json
# records what every endpoint returns. A change to the API has to change that
# file in the same commit, where a reviewer can see it.
#
# The file maps each endpoint to the shape of its response body:
#   "int", "str", "bool", "null"  a JSON value of that type
#   "datetime"                    a string in the API's datetime format
#   "int|null"                    either of these, in alphabetical order
#   {"field": shape, ...}         an object with exactly these fields
#   [shape]                       an array of values with this shape
#   {"null|object": {...}}        null or an object with these fields

import json
import os
import re

import pytest

with open(os.path.join(os.path.dirname(__file__), 'data', 'api_schema.json')) as f:
    SCHEMA = json.load(f)

ENDPOINTS = sorted(SCHEMA)

# DATETIME_FORMAT in settings.py
DATETIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+0000')

MISSING = object()


def shape(values):
    """Describe the JSON values seen in one place of a response, in the
    notation of api_schema.json"""
    kinds = set()
    objects = []
    items = []
    for value in values:
        if value is MISSING:
            kinds.add('missing')
        elif value is None:
            kinds.add('null')
        elif isinstance(value, bool):
            kinds.add('bool')
        elif isinstance(value, int):
            kinds.add('int')
        elif isinstance(value, float):
            kinds.add('float')
        elif isinstance(value, str):
            kinds.add('datetime' if DATETIME.fullmatch(value) else 'str')
        elif isinstance(value, dict):
            kinds.add('object')
            objects.append(value)
        else:
            kinds.add('array')
            items.extend(value)
    name = '|'.join(sorted(kinds))
    if objects:
        fields = {}
        for obj in objects:
            for key in obj:
                if key not in fields:
                    fields[key] = shape([o.get(key, MISSING) for o in objects])
        return fields if name == 'object' else {name: fields}
    if 'array' in kinds:
        inner = [shape(items)] if items else []
        return inner if name == 'array' else {name: inner}
    return name


def rows(body):
    """The records in a list response, paginated or not"""
    return body['results'] if isinstance(body, dict) else body


@pytest.fixture
def api(client, seeded_index):
    """Fetch an API URL the way BitBake does: no Accept header and no format
    parameter, expecting JSON"""
    def get(path, **params):
        response = client.get('/layerindex/api/' + path, params)
        assert response.status_code == 200, path
        assert response['Content-Type'] == 'application/json', path
        return response.json()
    return get


def test_root_links_to_every_endpoint(api):
    # Clients append "?filter=..." to these links
    assert api('') == {name: 'http://testserver/layerindex/api/%s/' % name for name in ENDPOINTS}


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_list_response_shape(api, endpoint):
    body = api(endpoint + '/')
    assert rows(body), 'the seeded index has no data for %s' % endpoint
    seen = shape([body])
    assert seen == SCHEMA[endpoint], (
        'The %s response changed. If that is intended, update tests/data/api_schema.json to:\n%s'
        % (endpoint, json.dumps(seen, indent=4)))


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_detail_response_matches_list(api, endpoint):
    for row in rows(api(endpoint + '/')):
        assert api('%s/%d/' % (endpoint, row['id'])) == row


def test_format_parameter_is_accepted(api):
    assert api('branches/', format='json') == api('branches/')
