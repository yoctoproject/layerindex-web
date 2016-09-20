# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.


import settings
from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),

    # override the default auth urls since django-registration 1.0 isn't Django 1.6 compatible
    url(r'^password/change/$',
                auth_views.password_change,
                name='password_change'),
    url(r'^password/change/done/$',
                auth_views.password_change_done,
                name='password_change_done'),
    url(r'^password/reset/$',
                auth_views.password_reset,
                name='password_reset'),
    url(r'^password/reset/done/$',
                auth_views.password_reset_done,
                name='password_reset_done'),
    url(r'^password/reset/complete/$',
                auth_views.password_reset_complete,
                name='password_reset_complete'),
    url(r'^password/reset/confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
                auth_views.password_reset_confirm,
                name='auth_password_reset_confirm'),

    url(r'^accounts/', include('registration.backends.default.urls')),
    url(r'^captcha/', include('captcha.urls')),
)

if settings.APPLICATION == 'layerindex':
    urlpatterns += patterns('',
        url(r'^layerindex/', include('layerindex.urls')),
        url(r'.*', RedirectView.as_view(url='/layerindex/', permanent=False)),
    )
elif settings.APPLICATION == 'rrs':
    urlpatterns += patterns('',
        url(r'^rrs/', include('rrs.urls')),
        url(r'.*', RedirectView.as_view(url='/rrs/', permanent=False)),
    )
