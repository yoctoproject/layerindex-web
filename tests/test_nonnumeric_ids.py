# layerindex-web - tests for non-numeric ids in URLs
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# [YOCTO #16519]: a non-numeric id in a URL or in the branch_comparison
# parameters reached the database as an id and raised ValueError (a 500).

import pytest
from django.test import TestCase

from layerindex.models import Branch, LayerItem


@pytest.mark.django_db
class TestNonNumericIds(TestCase):

    def assert_not_found(self, url, params=None):
        response = self.client.get(url, params or {})
        self.assertEqual(response.status_code, 404, (url, params))

    def test_recipe(self):
        for pk in ('NaN', '_', '1e400', 'true', 'é'):
            self.assert_not_found('/layerindex/recipe/%s/' % pk)

    def test_classic_recipe(self):
        self.assert_not_found('/layerindex/oe-classic/recipe/x/')

    def test_comparison_recipe(self):
        self.assert_not_found('/layerindex/comparison/recipe/x/')

    def test_branch_comparison(self):
        branch = Branch.objects.create(name='testbranch', bitbake_branch='master',
                                       short_description='Test', sort_priority=1)
        for value in ('', 'x', '²'):
            for url in ('/layerindex/branch_comparison/', '/layerindex/branch_comparison_plain/'):
                self.assert_not_found(url, {'from_branch': value, 'to_branch': branch.id})
                self.assert_not_found(url, {'from_branch': branch.id, 'to_branch': value})

    def test_branch_comparison_valid(self):
        branch = Branch.objects.create(name='testbranch', bitbake_branch='master',
                                       short_description='Test', sort_priority=1)
        # The comparison shows the core layer by default
        LayerItem.objects.create(name='openembedded-core', status='P', layer_type='A',
                                 summary='core', description='core',
                                 vcs_url='git://example.com/oe-core.git')
        response = self.client.get('/layerindex/branch_comparison/', {'from_branch': branch.id})
        self.assertEqual(response.status_code, 200)
