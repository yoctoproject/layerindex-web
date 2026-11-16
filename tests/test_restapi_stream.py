# layerindex-web - tests for streamed REST API lists
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# An unpaginated list is sent a chunk at a time, so a whole table never has to
# be built in memory, and the JSON is the same as before. tests/test_api_contract.py
# checks the shape of the streamed responses.

import json
from unittest import mock

from layerindex.models import Recipe
from layerindex.restviews import ParametricSearchableModelViewSet, RecipeSerializer


def get_recipes(client, **params):
    return client.get('/layerindex/api/recipes/', params)


def content(response):
    return b''.join(response.streaming_content)


def test_streamed_in_chunks(client, seeded_index):
    # Chunks of 3 for 4 recipes: the last chunk is short
    with mock.patch.object(ParametricSearchableModelViewSet, 'stream_chunk_size', 3):
        response = get_recipes(client, format='json')
        assert response.status_code == 200
        assert response.streaming
        assert response['Content-Type'] == 'application/json'
        data = json.loads(content(response))
    expected = RecipeSerializer(Recipe.objects.order_by('id'), many=True).data
    assert data == json.loads(json.dumps(expected))


def test_whole_chunks(client, seeded_index):
    with mock.patch.object(ParametricSearchableModelViewSet, 'stream_chunk_size', 2):
        data = json.loads(content(get_recipes(client, format='json')))
    assert len(data) == Recipe.objects.count() == 4


def test_empty_list(client, seeded_index):
    assert content(get_recipes(client, format='json', filter='pn:nosuchrecipe')) == b'[]'


def test_filter_still_applies(client, seeded_index):
    data = json.loads(content(get_recipes(client, format='json', filter='pn:base-example')))
    assert [r['pn'] for r in data] == ['base-example']


def test_paginated_list_not_streamed(client, seeded_index):
    response = client.get('/layerindex/api/recipesExtended/', {'format': 'json'})
    assert response.status_code == 200
    assert not response.streaming
    assert response.json()['count'] == 4


def test_browsable_api_not_streamed(client, seeded_index):
    response = client.get('/layerindex/api/recipes/', HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    assert not response.streaming
