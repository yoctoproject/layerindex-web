# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.

from django.conf.urls import include, url
from django.urls import reverse_lazy
from django.views.generic import RedirectView, TemplateView
from layerindex.auth_views import CaptchaRegistrationView, CaptchaPasswordResetView, delete_account_view, \
    PasswordResetSecurityQuestions
from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = [
    url(r'^layerindex/', include('layerindex.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/password_reset/$',
        CaptchaPasswordResetView.as_view(
            email_template_name='registration/password_reset_email.txt',
            success_url=reverse_lazy('password_reset_done')),
        name='password_reset'),
    url(r'^accounts/register/$', CaptchaRegistrationView.as_view(),
        name='django_registration_register'),
    url(r'^accounts/delete/$', delete_account_view,
        {'template_name': 'layerindex/deleteaccount.html'},
        name='delete_account'),
    url(r'^accounts/reregister/$', TemplateView.as_view(
        template_name='registration/reregister.html'),
        name='reregister'),
    url(r'^accounts/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,3}-[0-9A-Za-z]{1,20})/$',
        PasswordResetSecurityQuestions.as_view(),
        name='password_reset_confirm',
        ),
    url(r'^accounts/reset/fail/$', TemplateView.as_view(
        template_name='registration/password_reset_fail.html'),
        name='password_reset_fail'),
    url(r'^accounts/lockout/$', TemplateView.as_view(
        template_name='registration/account_lockout.html'),
        name='account_lockout'),
    url(r'^accounts/', include('django_registration.backends.activation.urls')),
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^captcha/', include('captcha.urls')),
]
if 'rrs' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^rrs/', include('rrs.urls')),
    ]

urlpatterns += [
    url(r'.*', RedirectView.as_view(url='/layerindex/', permanent=False)),
]
