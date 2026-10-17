# layerindex-web - tests for the account activation email and page
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django_registration.backends.activation.views import RegistrationView


@pytest.mark.django_db
class TestAccountActivation(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('newuser', 'new@example.com', 'pw', is_active=False)

    def _activation_path(self):
        view = RegistrationView()
        view.request = RequestFactory().get('/')
        view.send_activation_email(self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])
        match = re.search(r'https?://[^/\s]+(/\S+)', mail.outbox[0].body)
        self.assertIsNotNone(match, mail.outbox[0].body)
        return match.group(1)

    def test_activation_link_activates_account(self):
        path = self._activation_path()
        self.assertTrue(path.startswith(reverse('django_registration_activate') + '?activation_key='))

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'activation_form')

        key = response.context['form']['activation_key'].value()
        response = self.client.post(reverse('django_registration_activate'), {'activation_key': key})
        self.assertRedirects(response, reverse('django_registration_activation_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_invalid_key_does_not_activate(self):
        response = self.client.post(reverse('django_registration_activate'), {'activation_key': 'bogus'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid or has expired')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
