# layerindex-web - RSS feed definitions
#
# Copyright (C) 2026 Qbee AS
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.contrib.sites.models import Site
from django.contrib.syndication.views import Feed
from django.urls import reverse

from layerindex.models import LayerItem

class PublishedLayersFeed(Feed):
    """The most recently published layers, newest first."""
    max_items = 50

    def title(self):
        site = Site.objects.get_current()
        if site and site.name and site.name != 'example.com':
            site_name = site.name
        else:
            site_name = 'OpenEmbedded Layer Index'


        # Same form as the page titles in base.html
        return '%s - recently published layers' % site_name

    def description(self):
        return 'Recently published layers'

    def link(self):
        return reverse('layer_list', args=('master',))

    def items(self):
        # Layers published before the published field existed have no date
        # and are deliberately left out (see migration 0059). Only the fields
        # used below are loaded.
        return LayerItem.objects.filter(
            status='P', comparison=False, published__isnull=False,
        ).order_by('-published', 'name').only(
            'name', 'summary', 'published')[:self.max_items]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        return item.summary

    def item_pubdate(self, item):
        return item.published
