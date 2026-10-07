# layerindex-web - tests for sitemap.xml
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.test import TestCase

from layerindex.models import LayerItem


@pytest.mark.django_db
class TestSitemap(TestCase):

    def _layer(self, name, status='P', comparison=False):
        return LayerItem.objects.create(
            name=name,
            status=status,
            layer_type='A',
            summary=name,
            description=name,
            vcs_url='git://example.com/%s.git' % name,
            comparison=comparison,
        )

    def test_sitemap(self):
        self._layer('meta-published')
        self._layer('meta-new', status='N')
        self._layer('meta-compare', comparison=True)

        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('/layerindex/branch/master/layer/meta-published/', content)
        self.assertIn('/layerindex/about/', content)
        self.assertNotIn('meta-new', content)
        self.assertNotIn('meta-compare', content)
