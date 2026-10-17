# layerindex-web - tests for bulk change access control
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from layerindex.models import RecipeChangeset


@pytest.mark.django_db
class TestBulkChangeAccess(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pw')
        self.other = User.objects.create_user('other', 'other@example.com', 'pw')
        self.changeset = RecipeChangeset.objects.create(user=self.owner, name='mine')

    def _url(self, name):
        return reverse(name, args=(self.changeset.pk,))

    def test_anonymous_redirected_to_login(self):
        for name in ('bulk_change_edit', 'bulk_change_review', 'bulk_change_patches', 'bulk_change_delete'):
            response = self.client.get(self._url(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('login', response['Location'], name)

    def test_other_user_gets_404(self):
        self.client.force_login(self.other)
        for name in ('bulk_change_edit', 'bulk_change_review', 'bulk_change_patches', 'bulk_change_delete'):
            response = self.client.get(self._url(name))
            self.assertEqual(response.status_code, 404, name)
        response = self.client.post(self._url('bulk_change_delete'))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(RecipeChangeset.objects.filter(pk=self.changeset.pk).exists())

    def test_other_user_cannot_post_edits(self):
        self.client.force_login(self.other)
        # A valid (empty) edit formset, which would be saved and redirect
        # to the review page if the changeset were found
        data = {'form-TOTAL_FORMS': '0', 'form-INITIAL_FORMS': '0'}
        response = self.client.post(self._url('bulk_change_edit'), data)
        self.assertEqual(response.status_code, 404)

    def test_owner_can_access(self):
        self.client.force_login(self.owner)
        for name in ('bulk_change_edit', 'bulk_change_review'):
            response = self.client.get(self._url(name))
            self.assertEqual(response.status_code, 200, name)
