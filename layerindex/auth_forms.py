# layerindex-web - extended authentication forms
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django_registration.forms import RegistrationForm

from layerindex.models import SecurityQuestion


class CaptchaRegistrationForm(RegistrationForm):
    captcha = CaptchaField(label='Verification',
                           help_text='Please enter the letters displayed for verification purposes',
                           error_messages={'invalid':'Incorrect entry, please try again'})
    security_question_1 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_1 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True)
    security_question_2 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_2 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True)
    security_question_3 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_3 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True)

    def __init__(self, *args, **kwargs):
        super(CaptchaRegistrationForm, self ).__init__(*args, **kwargs)
        self.fields['security_question_1'].initial=SecurityQuestion.objects.all()[0]
        self.fields['security_question_2'].initial=SecurityQuestion.objects.all()[1]
        self.fields['security_question_3'].initial=SecurityQuestion.objects.all()[2]

    def clean(self):
        cleaned_data = super(CaptchaRegistrationForm, self).clean()
        security_question_1 = self.cleaned_data["security_question_1"]
        security_question_2 = self.cleaned_data["security_question_2"]
        security_question_3 = self.cleaned_data["security_question_3"]
        if security_question_1 == security_question_2:
            raise forms.ValidationError({'security_question_2': ["Questions may only be chosen once."]})
        if security_question_1 == security_question_3 or security_question_2 == security_question_3:
            raise forms.ValidationError({'security_question_3': ["Questions may only be chosen once."]})
        return cleaned_data

    class Meta:
        model = User
        fields = [
            User.USERNAME_FIELD,
            'email',
            'password1',
            'password2',
        ]


class CaptchaPasswordResetForm(PasswordResetForm):
    captcha = CaptchaField(label='Verification',
                           help_text='Please enter the letters displayed for verification purposes',
                           error_messages={'invalid':'Incorrect entry, please try again'})


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


class SecurityQuestionPasswordResetForm(SetPasswordForm):
    correct_answers = 0
    security_question_1 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_1 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True,)
    security_question_2 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_2 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True)
    security_question_3 = forms.ModelChoiceField(queryset=SecurityQuestion.objects.all())
    answer_3 = forms.CharField(widget=forms.TextInput(), label='Answer', required=True)

    def __init__(self, *args, **kwargs):
        super(SecurityQuestionPasswordResetForm, self ).__init__(*args, **kwargs)
        self.fields['security_question_1'].initial=SecurityQuestion.objects.all()[0]
        self.fields['security_question_2'].initial=SecurityQuestion.objects.all()[1]
        self.fields['security_question_3'].initial=SecurityQuestion.objects.all()[2]

    def clean_answer_util(self, question, answer):
        form_security_question = self.cleaned_data[question]
        form_answer = self.cleaned_data[answer].replace(" ", "").lower()
        # Attempt to get the user's hashed answer to the security question. If the user didn't choose
        # this security question, throw an exception.
        try:
            question_answer = self.user.userprofile.securityquestionanswer_set.filter(
                security_question__question=form_security_question)[0]
        except IndexError as e:
            raise forms.ValidationError("Security question is incorrect.")
        user_answer = question_answer.answer

        # Compare input answer to hashed database answer.
        if check_password(form_answer, user_answer):
            self.correct_answers = self.correct_answers+1
        return form_answer

    def clean_answer_1(self):
        return self.clean_answer_util("security_question_1", "answer_1")

    def clean_answer_2(self):
        return self.clean_answer_util("security_question_2", "answer_2")

    def clean_answer_3(self):
        return self.clean_answer_util("security_question_3", "answer_3")

    def clean(self):
        # We require three correct security question answers. The user gets
        # three attempts before their account is locked out.
        answer_attempts = self.user.userprofile.answer_attempts
        if self.correct_answers < 3:
            if answer_attempts < 2:
                self.user.userprofile.answer_attempts = self.user.userprofile.answer_attempts + 1
                self.user.userprofile.save()
                raise forms.ValidationError("One or more security answers are incorrect.", code="incorrect_answers")
            else :
                # Reset answer attempts to 0 and throw error to lock account.
                self.user.userprofile.answer_attempts = 0
                self.user.userprofile.save()
                raise forms.ValidationError("Too many attempts! Your account has been locked. "
                                            "Please contact your admin.", code="account_locked")

        else:
            self.user.userprofile.answer_attempts = 0
            self.user.userprofile.save()
