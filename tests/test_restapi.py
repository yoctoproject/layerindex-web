# layerindex-web - tests for the REST API
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import datetime
import json

import pytest
from django.test import TestCase

from layerindex.models import LayerItem


@pytest.mark.django_db
class TestRestApiDatetimes(TestCase):

    def test_datetime_format(self):
        layer = LayerItem.objects.create(name='meta-test', status='P', layer_type='A',
                                         summary='test', description='test',
                                         vcs_url='git://example.com/meta-test.git')
        # auto_now would overwrite a value passed to save()
        LayerItem.objects.filter(pk=layer.pk).update(updated=datetime.datetime(2026, 10, 18, 14, 37, 5))

        response = self.client.get('/layerindex/api/layerItems/', {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        # Unpaginated lists are streamed
        data = json.loads(b''.join(response.streaming_content))
        items = data['results'] if isinstance(data, dict) else data
        item = next(i for i in items if i['name'] == 'meta-test')
        self.assertEqual(item['updated'], '2026-10-18T14:37:05+0000')


@pytest.mark.django_db
class TestRestApiInvalidParameters(TestCase):
    """Invalid filter and orderby values give a 400 ([YOCTO #16517])"""

    def assert_bad_request(self, params):
        response = self.client.get('/layerindex/api/layerItems/', dict(params, format='json'))
        self.assertEqual(response.status_code, 400, params)

    def test_unknown_filter_field(self):
        # Raised BaseException, which killed the worker
        self.assert_bad_request({'filter': 'pn:x'})

    def test_filter_without_value(self):
        self.assert_bad_request({'filter': 'name'})

    def test_filter_value_of_wrong_type(self):
        # Raised ValueError: a 500
        self.assert_bad_request({'filter': 'id:abc'})

    def test_unknown_orderby_field(self):
        self.assert_bad_request({'orderby': 'pn:-'})

    def test_valid_filter(self):
        LayerItem.objects.create(name='meta-test', status='P', layer_type='A',
                                 summary='test', description='test',
                                 vcs_url='git://example.com/meta-test.git')
        response = self.client.get('/layerindex/api/layerItems/',
                                   {'filter': 'name:meta-test', 'format': 'json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i['name'] for i in json.loads(b''.join(response.streaming_content))],
                         ['meta-test'])


@pytest.mark.django_db
class TestRestApiOrderby(TestCase):
    """orderby sorts the results ([YOCTO #16518])"""

    def setUp(self):
        for name in ('meta-b', 'meta-a', 'meta-c'):
            LayerItem.objects.create(name=name, status='P', layer_type='A',
                                     summary='test', description='test',
                                     vcs_url='git://example.com/%s.git' % name)

    def names(self, orderby):
        response = self.client.get('/layerindex/api/layerItems/',
                                   {'orderby': orderby, 'format': 'json'})
        self.assertEqual(response.status_code, 200)
        return [i['name'] for i in json.loads(b''.join(response.streaming_content))]

    def test_ascending(self):
        self.assertEqual(self.names('name:+'), ['meta-a', 'meta-b', 'meta-c'])

    def test_descending(self):
        # DESCENDING in querysethelper.py
        self.assertEqual(self.names('name:-'), ['meta-c', 'meta-b', 'meta-a'])

    def test_unknown_related_field(self):
        # "layerbranch" passes the field-name check; the rest of the path is wrong
        response = self.client.get('/layerindex/api/layerItems/',
                                   {'orderby': 'layerbranch__nosuchfield:+', 'format': 'json'})
        self.assertEqual(response.status_code, 400)
