# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.

from django.conf.urls.defaults import patterns, include, url
from django.views.generic.simple import redirect_to

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^layerindex/', include('layerindex.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('registration.urls')),
    url(r'^captcha/', include('captcha.urls')),
    url(r'.*', redirect_to, {'url' : '/layerindex/'})
)

