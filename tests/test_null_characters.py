# layerindex-web - tests for NUL characters in requests
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# [YOCTO #16520]: PostgreSQL text can't hold NUL, so a search or URL with
# one raised DataError (a 500). MariaDB returned no results, so these tests
# check for the 400 rather than for the DataError.

import pytest
from django.test import TestCase

from layerindex.models import Branch


@pytest.mark.django_db
class TestNullCharacters(TestCase):

    def setUp(self):
        # The migrations may have created it already
        Branch.objects.get_or_create(name='master', defaults=dict(
            bitbake_branch='master', short_description='Master', sort_priority=1))

    def assert_bad_request(self, url, params=None):
        response = self.client.get(url, params or {})
        self.assertEqual(response.status_code, 400, (url, params))

    def test_search(self):
        self.assert_bad_request('/layerindex/branch/master/recipes/', {'q': 'a\x00b'})

    def test_api_filter(self):
        self.assert_bad_request('/layerindex/api/recipes/', {'filter': 'pn:\x00'})

    def test_parameter_name(self):
        self.assert_bad_request('/layerindex/branch/master/recipes/', {'q\x00': 'a'})

    def test_path(self):
        self.assert_bad_request('/layerindex/branch/master/layer/a%00b/')

    def test_search_without_nul(self):
        response = self.client.get('/layerindex/branch/master/recipes/', {'q': 'ab'})
        self.assertEqual(response.status_code, 200)
