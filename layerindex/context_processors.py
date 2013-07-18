# layerindex-web - custom context processor
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import Branch, LayerItem

def layerindex_context(request):
    return {
        'all_branches': Branch.objects.exclude(name='oe-classic').order_by('sort_priority'),
        'unpublished_count': LayerItem.objects.filter(status='N').count(),
        'oe_classic': Branch.objects.filter(name='oe-classic')
    }