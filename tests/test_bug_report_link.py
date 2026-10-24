# layerindex-web - tests for the bug report link
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.test import TestCase
from django.urls import reverse

BUG_URL = 'https://bugzilla.yoctoproject.org/enter_bug.cgi?product=Layer%20Index'


@pytest.mark.django_db
class TestBugReportLink(TestCase):

    def test_footer_links_to_bugzilla(self):
        response = self.client.get(reverse('history_list'))
        self.assertContains(response, '<a href="%s">report a bug</a>' % BUG_URL)

    def test_about_page_links_to_bugzilla(self):
        response = self.client.get(reverse('about'))
        self.assertContains(response, '<a href="%s">report it</a>' % BUG_URL)
