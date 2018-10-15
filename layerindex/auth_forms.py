# layerindex-web - extended authentication forms
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from captcha.fields import CaptchaField
from registration.forms import RegistrationForm
from django.contrib.auth.forms import PasswordResetForm


class CaptchaRegistrationForm(RegistrationForm):
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})

class CaptchaPasswordResetForm(PasswordResetForm):
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})
