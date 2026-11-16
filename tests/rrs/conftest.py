# layerindex-web - fixtures for the tests that need the RRS app
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# RRS is optional (ENABLE_RRS=1 in docker/settings.py). Without it these tests
# are not collected; docker/run-tests.sh runs them in a second pass with it.

import datetime
import types

import pytest
from django.conf import settings

if 'rrs' not in settings.INSTALLED_APPS:
    collect_ignore_glob = ['test_*.py']


@pytest.fixture
def rrs_plan(db):
    """A maintenance plan "OE-Core" on the core layer's master branch, with
    release 6.2 and its milestone M1 (October to December 2026)"""
    from layerindex.models import Branch, LayerBranch, LayerItem
    from rrs.models import (
        Maintainer,
        MaintenancePlan,
        MaintenancePlanLayerBranch,
        Milestone,
        Release,
    )

    # Created by rrs/migrations/0001_initial.py, which --nomigrations skips
    for name in ('No maintainer', 'All'):
        Maintainer.objects.get_or_create(name=name)

    branch, _ = Branch.objects.get_or_create(name='master', defaults={'bitbake_branch': 'master'})
    layer = LayerItem.objects.create(name='openembedded-core', status='P', layer_type='A',
                                     summary='Core metadata', description='Core metadata',
                                     vcs_url='https://git.example.com/openembedded-core')
    layerbranch = LayerBranch.objects.create(layer=layer, branch=branch)
    plan = MaintenancePlan.objects.create(name='OE-Core')
    MaintenancePlanLayerBranch.objects.create(plan=plan, layerbranch=layerbranch)
    release = Release.objects.create(plan=plan, name='6.2', start_date=datetime.date(2026, 10, 1),
                                     end_date=datetime.date(2027, 4, 30))
    milestone = Milestone.objects.create(release=release, name='M1',
                                         start_date=datetime.date(2026, 10, 1),
                                         end_date=datetime.date(2026, 12, 31))
    return types.SimpleNamespace(layerbranch=layerbranch, plan=plan, release=release,
                                 milestone=milestone)
