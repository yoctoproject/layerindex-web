# layerindex-web - URLs
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.

from django.conf.urls import include, url
from django.views.generic import RedirectView

from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = [
    url(r'^layerindex/', include('layerindex.urls')),
    url(r'^admin/', include(admin.site.urls)),
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
