# layerindex-web - tests for showing layer dependencies
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.test import TestCase
from django.urls import reverse

from layerindex.models import Branch, LayerBranch, LayerDependency, LayerItem


@pytest.mark.django_db
class TestLayerDependencies(TestCase):

    def make_layer(self, name):
        return LayerItem.objects.create(name=name, status='P', layer_type='A',
                                        summary='test', description='test',
                                        vcs_url='git://example.com/%s.git' % name)

    def setUp(self):
        master, _ = Branch.objects.get_or_create(name='master', defaults={'bitbake_branch': 'master'})
        other = Branch.objects.create(name='other', bitbake_branch='master')
        top = self.make_layer('meta-top')
        dep = self.make_layer('meta-dep')
        # Create layer branches on another branch first, so that meta-dep's
        # LayerItem and LayerBranch ids differ
        LayerBranch.objects.create(layer=top, branch=other)
        LayerBranch.objects.create(layer=dep, branch=other)
        self.dep_layerbranch = LayerBranch.objects.create(layer=dep, branch=master)
        top_layerbranch = LayerBranch.objects.create(layer=top, branch=master)
        self.dependency = LayerDependency.objects.create(layerbranch=top_layerbranch, dependency=dep)
        self.assertNotEqual(dep.id, self.dep_layerbranch.id)

    def test_dependency_layerbranch(self):
        self.assertEqual(self.dependency.dependency_layerbranch(), self.dep_layerbranch)

    def test_detail_page_lists_dependency_layerbranch(self):
        response = self.client.get(reverse('layer_item', args=('master', 'meta-top')))
        self.assertContains(response, '<li data-layerbranch="%d">' % self.dep_layerbranch.id)
