# layerindex-web - extended authentication views
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import (PasswordResetConfirmView,
                                       PasswordResetView)
from django.contrib.sites.shortcuts import get_current_site

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_registration import signals
from django_registration.backends.activation.views import RegistrationView

from layerindex.auth_forms import (CaptchaPasswordResetForm,
                                   CaptchaRegistrationForm, DeleteAccountForm,
                                   SecurityQuestionPasswordResetForm)

from .models import SecurityQuestion, SecurityQuestionAnswer, UserProfile
from . import tasks
import settings

@method_decorator(never_cache, name='dispatch')
class CaptchaRegistrationView(RegistrationView):
    form_class = CaptchaRegistrationForm

    def register(self, form):
        new_user = self.create_inactive_user(form)
        signals.user_registered.send(
            sender=self.__class__,
            user=new_user,
            request=self.request
        )

        # Add security question answers to the database
        security_question_1 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_1"))
        security_question_2 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_2"))
        security_question_3 = SecurityQuestion.objects.get(question=form.cleaned_data.get("security_question_3"))
        answer_1 = form.cleaned_data.get("answer_1").replace(" ", "").lower()
        answer_2 = form.cleaned_data.get("answer_2").replace(" ", "").lower()
        answer_3 = form.cleaned_data.get("answer_3").replace(" ", "").lower()

        user = UserProfile.objects.create(user=new_user)
        # Answers are hashed using Django's password hashing function make_password()
        SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_1,
                                              answer=make_password(answer_1))
        SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_2,
                                              answer=make_password(answer_2))
        SecurityQuestionAnswer.objects.create(user=user, security_question=security_question_3,
                                              answer=make_password(answer_3))

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


@method_decorator(never_cache, name='dispatch')
class CaptchaPasswordResetView(PasswordResetView):
    form_class = CaptchaPasswordResetForm


def delete_account_view(request, template_name):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if request.user.is_superuser:
        # It's not really appropriate for the superuser to be deleted this way
        raise PermissionDenied
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST, instance=request.user)
        if form.is_valid():
            # Naturally we don't call form.save() here !
            # Take a copy of request.user as it is about to be invalidated by logout()
            user = request.user
            logout(request)
            user.delete()
            messages.add_message(request, messages.SUCCESS,
                            'Your user account has been successfully deleted')
            return HttpResponseRedirect(reverse('frontpage'))
    else:
        form = DeleteAccountForm(instance=request.user)

    return render(request, template_name, {
        'user': request.user,
        'form': form,
    })


class PasswordResetSecurityQuestions(PasswordResetConfirmView):
    form_class = SecurityQuestionPasswordResetForm

    def get(self, request, *args, **kwargs):
        try:
            self.user.userprofile
        except UserProfile.DoesNotExist:
            if getattr(settings, 'SECURITY_QUESTIONS_REQUIRED', True):
                return HttpResponseRedirect(reverse('password_reset_fail'))
        if not self.user.is_active:
            return HttpResponseRedirect(reverse('account_lockout'))

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.form_class(data=request.POST, user=self.user)
        form.is_valid()
        for error in form.non_field_errors().as_data():
            if error.code == "account_locked":
                # Deactivate user's account.
                self.user.is_active = False
                self.user.save()
                # Send admin an email that user is locked out.
                site_name = get_current_site(request).name
                subject = "User account locked on " + site_name
                text_content = "User " + self.user.username + " has been locked out on " + site_name + "."
                admins = settings.ADMINS
                from_email = settings.DEFAULT_FROM_EMAIL
                tasks.send_email.apply_async((subject, text_content, from_email, [a[1] for a in admins]))
                return HttpResponseRedirect(reverse('account_lockout'))

            if error.code == "incorrect_answers":
                # User has failed first attempt at answering questions, give them another try.
                return self.form_invalid(form)

        return super().post(request, *args, **kwargs)
