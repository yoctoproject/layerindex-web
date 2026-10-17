# layerindex-web - tests for the layer recipes CSV export
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.test import TestCase
from django.urls import reverse

from layerindex.models import Branch, LayerItem, LayerBranch


@pytest.mark.django_db
class TestRecipesCsv(TestCase):

    def setUp(self):
        branch = Branch.objects.create(name='master', bitbake_branch='master')
        layer = LayerItem.objects.create(name='meta-test', status='P', layer_type='A',
                                         summary='test', description='test',
                                         vcs_url='git://example.com/meta-test.git')
        LayerBranch.objects.create(layer=layer, branch=branch)
        self.url = reverse('layer_export_recipes_csv', args=('master', 'meta-test'))

    def test_valid_fields(self):
        response = self.client.get(self.url, {'fields': 'pn,pv'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))

    def test_invalid_field_not_reflected_as_html(self):
        response = self.client.get(self.url, {'fields': '<script>alert(1)</script>'})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response['Content-Type'].startswith('text/plain'))
