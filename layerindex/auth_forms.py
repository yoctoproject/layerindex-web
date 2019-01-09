# layerindex-web - extended authentication forms
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django import forms
from captcha.fields import CaptchaField
from django_registration.forms import RegistrationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password


class CaptchaRegistrationForm(RegistrationForm):
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})

class CaptchaPasswordResetForm(PasswordResetForm):
    captcha = CaptchaField(label='Verification', help_text='Please enter the letters displayed for verification purposes', error_messages={'invalid':'Incorrect entry, please try again'})


class DeleteAccountForm(forms.ModelForm):
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('confirm_password', )

    def clean(self):
        cleaned_data = super(DeleteAccountForm, self).clean()
        confirm_password = cleaned_data.get('confirm_password')
        if not check_password(confirm_password, self.instance.password):
            self.add_error('confirm_password', 'Password does not match.')
        return cleaned_data
