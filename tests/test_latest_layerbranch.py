# layerindex-web - tests for choosing the layer branch to copy settings from
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import pytest
from django.test import TestCase

from layerindex.models import Branch, LayerBranch, LayerItem


@pytest.mark.django_db
class TestLatestLayerBranch(TestCase):
    """When a layer is first seen on a new branch, the update script copies
    vcs_subdir from an existing layer branch. It must use the newest branch:
    meta-tq moved into a meta-tq/ subdirectory, and copying the empty
    subdirectory of an old branch made the new branch's update fail with
    "conf/layer.conf not found"."""

    def setUp(self):
        self.layer = LayerItem.objects.create(name='meta-tq', status='P', layer_type='B',
                                              summary='test', description='test',
                                              vcs_url='https://example.com/meta-tq.git')

    def branch(self, name, sort_priority, comparison=False):
        return Branch.objects.create(name=name, bitbake_branch=name, sort_priority=sort_priority,
                                     comparison=comparison)

    def layerbranch(self, branch, subdir):
        return LayerBranch.objects.create(layer=self.layer, branch=branch, vcs_subdir=subdir)

    def test_newest_branch_wins_over_oldest_record(self):
        # Oldest branch first, so it is the first record (as for meta-tq)
        self.layerbranch(self.branch('krogoth', 20), '')
        self.layerbranch(self.branch('kirkstone', 5), 'meta-tq')
        newest = self.layerbranch(self.branch('scarthgap', 3), 'meta-tq')
        self.assertEqual(self.layer.get_latest_layerbranch(), newest)
        self.assertEqual(self.layer.get_latest_layerbranch().vcs_subdir, 'meta-tq')

    def test_comparison_and_unprioritised_branches_are_not_preferred(self):
        self.layerbranch(self.branch('comparison', 1, comparison=True), 'other')
        self.layerbranch(self.branch('unsorted', None), 'other')
        newest = self.layerbranch(self.branch('scarthgap', 3), 'meta-tq')
        self.assertEqual(self.layer.get_latest_layerbranch(), newest)

    def test_only_unprioritised_branches(self):
        lb = self.layerbranch(self.branch('unsorted', None), 'meta-tq')
        self.assertEqual(self.layer.get_latest_layerbranch(), lb)

    def test_no_layer_branches(self):
        self.assertIsNone(self.layer.get_latest_layerbranch())
