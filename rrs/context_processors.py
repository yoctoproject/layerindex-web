# rrs-web - custom context processor
#
# Copyright (C) 2014 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import settings
from django.contrib.sites.models import Site

def rrs_context(request):
    site = Site.objects.get_current()
    if site and site.name and site.name != 'example.com':
        site_name = site.name
    else:
        site_name = 'Recipe reporting system'
    return {
        'site_name': site_name,
        'application' : settings.APPLICATION
    }
