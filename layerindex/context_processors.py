# layerindex-web - custom context processor
#
# Copyright (C) 2013, 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import Branch, LayerItem, SiteNotice
from django.contrib.sites.models import Site
from django.db.models import Q
from datetime import datetime

def layerindex_context(request):
    import settings
    site = Site.objects.get_current()
    if site and site.name and site.name != 'example.com':
        site_name = site.name
    else:
        site_name = 'OpenEmbedded Layer Index'
    if request.path.startswith('/accounts'):
        login_return_url = ''
    else:
        login_return_url = request.path
    return {
        'all_branches': Branch.objects.exclude(comparison=True).exclude(hidden=True).order_by('sort_priority'),
        'unpublished_count': LayerItem.objects.filter(status='N').count(),
        'site_name': site_name,
        'rrs_enabled': 'rrs' in settings.INSTALLED_APPS,
        'notices': SiteNotice.objects.filter(disabled=False).filter(Q(expires__isnull=True) | Q(expires__gte=datetime.now())),
        'comparison_branches': Branch.objects.filter(comparison=True).exclude(hidden=True),
        'login_return_url': login_return_url,
    }
