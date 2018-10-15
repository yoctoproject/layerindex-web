# layerindex-web - extended authentication views
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from registration.backends.model_activation.views import RegistrationView
from django.contrib.auth.views import PasswordResetView
from layerindex.auth_forms import CaptchaRegistrationForm, CaptchaPasswordResetForm


class CaptchaRegistrationView(RegistrationView):
    form_class = CaptchaRegistrationForm

    def get_context_data(self, **kwargs):
        context = super(CaptchaRegistrationView, self).get_context_data(**kwargs)
        form = context['form']
        # Prepare a list of fields with errors
        # We do this so that if there's a problem with the captcha, that's the only error shown
        # (since we have a username field, we want to make user enumeration difficult)
        if 'captcha' in form.errors:
            error_fields = ['captcha']
        else:
            error_fields = form.errors.keys()
        context['error_fields'] = error_fields
        return context


class CaptchaPasswordResetView(PasswordResetView):
    form_class = CaptchaPasswordResetForm
