# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.

from django.conf.urls import include, url
from django.core.urlresolvers import reverse_lazy
from django.views.generic import RedirectView, TemplateView
from layerindex.auth_views import CaptchaRegistrationView, CaptchaPasswordResetView, delete_account_view

from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = [
    url(r'^layerindex/', include('layerindex.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/password/reset/$',
        CaptchaPasswordResetView.as_view(
            email_template_name='registration/password_reset_email.txt',
            success_url=reverse_lazy('auth_password_reset_done')),
        name='auth_password_reset'),
    url(r'^accounts/register/$', CaptchaRegistrationView.as_view(),
        name='registration_register'),
    url(r'^accounts/delete/$', delete_account_view,
        {'template_name': 'layerindex/deleteaccount.html'},
        name='delete_account'),
    url(r'^accounts/reregister/$', TemplateView.as_view(
        template_name='registration/reregister.html'),
        name='reregister'),
    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^captcha/', include('captcha.urls')),
]

if 'rrs' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^rrs/', include('rrs.urls')),
    ]

urlpatterns += [
    url(r'.*', RedirectView.as_view(url='/layerindex/', permanent=False)),
]
