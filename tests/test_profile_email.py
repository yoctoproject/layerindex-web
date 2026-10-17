# layerindex-web - tests for changing the email address on the profile page
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from captcha.models import CaptchaStore
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse

from layerindex.models import SecurityQuestion, SecurityQuestionAnswer, UserProfile


@pytest.mark.django_db
class TestProfileEmailChange(TestCase):
    """Changing the email address must not take effect without proving
    ownership of the new address, since layer edit rights are granted by
    matching the user's email against (public) maintainer emails."""

    def setUp(self):
        self.user = User.objects.create_user('someone', 'old@example.com', 'pw')
        profile = UserProfile.objects.create(user=self.user)
        self.questions = [SecurityQuestion.objects.create(question='Question %d' % i) for i in range(3)]
        for question in self.questions:
            SecurityQuestionAnswer.objects.create(user=profile, security_question=question, answer='x')
        self.client.force_login(self.user)

    def _post_profile(self, email):
        hashkey = CaptchaStore.generate_key()
        data = {
            'username': 'someone',
            'first_name': '',
            'last_name': '',
            'email': email,
            'captcha_0': hashkey,
            'captcha_1': CaptchaStore.objects.get(hashkey=hashkey).response,
            'answer_1': '*****',
            'answer_2': '*****',
            'answer_3': '*****',
        }
        for i, question in enumerate(self.questions, 1):
            data['security_question_%d' % i] = question.pk
        return self.client.post(reverse('profile'), data)

    def test_email_change_requires_reactivation(self):
        response = self._post_profile('maintainer@example.com')
        self.assertRedirects(response, reverse('reregister'), fetch_redirect_response=False)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        # Logged out, and an inactive account cannot log back in
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertIsNone(authenticate(RequestFactory().post('/'), username='someone', password='pw'))
        # The activation link only goes to the new address
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maintainer@example.com'])

    def test_unchanged_email_keeps_account_active(self):
        response = self._post_profile('old@example.com')
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(len(mail.outbox), 0)
