# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.

<<<<<<< HEAD
import settings

from django.conf.urls.defaults import patterns, include, url
from django.views.generic.simple import redirect_to
=======
from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView
>>>>>>> 5c17970... Upgrade to Django 1.6+

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
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
