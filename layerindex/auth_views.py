# layerindex-web - extended authentication views
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth import logout
from django_registration.backends.activation.views import RegistrationView
from django.contrib.auth.views import PasswordResetView
from layerindex.auth_forms import CaptchaRegistrationForm, CaptchaPasswordResetForm, DeleteAccountForm


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


def delete_account_view(request, template_name):
    if not request.user.is_authenticated():
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

