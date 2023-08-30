# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
#
# SPDX-License-Identifier: MIT

from django.urls import include, re_path, reverse_lazy
from django.views.generic import RedirectView, TemplateView
from layerindex.auth_views import CaptchaRegistrationView, CaptchaPasswordResetView, delete_account_view, \
    PasswordResetSecurityQuestions
from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = [
    re_path(r'^layerindex/', include('layerindex.urls')),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^accounts/password_reset/$',
        CaptchaPasswordResetView.as_view(
            email_template_name='registration/password_reset_email.txt',
            success_url=reverse_lazy('password_reset_done')),
        name='password_reset'),
    re_path(r'^accounts/register/$', CaptchaRegistrationView.as_view(),
        name='django_registration_register'),
    re_path(r'^accounts/delete/$', delete_account_view,
        {'template_name': 'layerindex/deleteaccount.html'},
        name='delete_account'),
    re_path(r'^accounts/reregister/$', TemplateView.as_view(
        template_name='registration/reregister.html'),
        name='reregister'),
    re_path(r'^accounts/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,3}-[0-9A-Za-z]{1,20})/$',
        PasswordResetSecurityQuestions.as_view(),
        name='password_reset_confirm',
        ),
    re_path(r'^accounts/reset/fail/$', TemplateView.as_view(
        template_name='registration/password_reset_fail.html'),
        name='password_reset_fail'),
    re_path(r'^accounts/lockout/$', TemplateView.as_view(
        template_name='registration/account_lockout.html'),
        name='account_lockout'),
    re_path(r'^accounts/', include('django_registration.backends.activation.urls')),
    re_path(r'^accounts/', include('django.contrib.auth.urls')),
    re_path(r'^captcha/', include('captcha.urls')),
]
if 'rrs' in settings.INSTALLED_APPS:
    urlpatterns += [
        re_path(r'^rrs/', include('rrs.urls')),
    ]

urlpatterns += [
    re_path(r'.*', RedirectView.as_view(url='/layerindex/', permanent=False)),
]
