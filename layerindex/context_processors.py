# layerindex-web - custom context processor
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import Branch, LayerItem
from django.contrib.sites.models import Site

def layerindex_context(request):
    site = Site.objects.get_current()
    if site and site.name and site.name != 'example.com':
        site_name = site.name
    else:
        site_name = 'OpenEmbedded metadata index'
    return {
        'all_branches': Branch.objects.exclude(name='oe-classic').order_by('sort_priority'),
        'unpublished_count': LayerItem.objects.filter(status='N').count(),
        'oe_classic': Branch.objects.filter(name='oe-classic'),
        'site_name': site_name
    }