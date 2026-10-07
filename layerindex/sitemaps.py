# layerindex-web - sitemap definitions
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from layerindex.models import LayerItem

BRANCH_VIEWS = ('layer_list', 'recipe_search', 'machine_search', 'distro_search', 'class_search')


class StaticViewSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.5

    def items(self):
        return list(BRANCH_VIEWS) + ['about', 'stats']

    def location(self, item):
        if item in BRANCH_VIEWS:
            return reverse(item, args=('master',))
        return reverse(item)


class LayerSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return LayerItem.objects.filter(status='P', comparison=False).order_by('name')

    def lastmod(self, obj):
        return obj.updated
