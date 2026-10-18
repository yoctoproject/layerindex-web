# layerindex-web - tests for the REST API
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import datetime

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
        data = response.json()
        items = data['results'] if isinstance(data, dict) else data
        item = next(i for i in items if i['name'] == 'meta-test')
        self.assertEqual(item['updated'], '2026-10-18T14:37:05+0000')
