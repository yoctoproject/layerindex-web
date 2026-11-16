# layerindex-web - tests for the RRS maintainers page
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# The maintainers page shows each maintainer's recipe statistics and upgrades
# per week, and must get them without running queries per maintainer.

import datetime

from django.db import connection
from django.test.utils import CaptureQueriesContext

from rrs.models import (
    Maintainer,
    RecipeMaintainer,
    RecipeMaintainerHistory,
    RecipeSymbol,
    RecipeUpgrade,
    RecipeUpstream,
    RecipeUpstreamHistory,
)

URL = '/rrs/maintainers/OE-Core/6.2/M1/'
# USE_TZ is False
UPGRADE_DATE = datetime.datetime(2026, 11, 1)


def histories(layerbranch):
    author, _ = Maintainer.objects.get_or_create(name='No maintainer')
    maintainer_history = RecipeMaintainerHistory.objects.create(
        title='Update maintainers', date=datetime.datetime(2026, 10, 15), author=author,
        sha1='0' * 40, layerbranch=layerbranch)
    upstream_history = RecipeUpstreamHistory.objects.create(
        layerbranch=layerbranch, start_date=datetime.datetime(2026, 10, 20),
        end_date=datetime.datetime(2026, 10, 20, 1))
    return maintainer_history, upstream_history


def add_recipe(layerbranch, history, pn, maintainer_name, status, no_update_reason=''):
    """A recipe maintained by maintainer_name, with an upstream status and one upgrade"""
    maintainer_history, upstream_history = history
    maintainer, _ = Maintainer.objects.get_or_create(name=maintainer_name)
    symbol = RecipeSymbol.objects.create(layerbranch=layerbranch, pn=pn, summary=pn)
    RecipeMaintainer.objects.create(recipesymbol=symbol, maintainer=maintainer,
                                    history=maintainer_history)
    RecipeUpstream.objects.create(recipesymbol=symbol, history=upstream_history, version='2.0',
                                  type='A', status=status, no_update_reason=no_update_reason,
                                  date=upstream_history.end_date)
    RecipeUpgrade.objects.create(recipesymbol=symbol, maintainer=maintainer, version='1.0',
                                 author_date=UPGRADE_DATE, commit_date=UPGRADE_DATE,
                                 upgrade_type='U')


def maintainer_list(client):
    response = client.get(URL)
    assert response.status_code == 200
    return {ml.name: ml for ml in response.context['maintainer_list']}


def test_statistics(client, rrs_plan):
    history = histories(rrs_plan.layerbranch)
    add_recipe(rrs_plan.layerbranch, history, 'busybox', 'Alice', 'Y')
    add_recipe(rrs_plan.layerbranch, history, 'zlib', 'Alice', 'N')
    add_recipe(rrs_plan.layerbranch, history, 'gcc', 'Bob', 'N', 'Needs a newer binutils')

    maintainers = maintainer_list(client)

    alice, bob = maintainers['Alice'], maintainers['Bob']
    assert (alice.recipes_all, alice.recipes_up_to_date, alice.recipes_not_updated,
            alice.recipes_cant_be_updated, alice.percentage_done) == (2, 1, 1, '', '50%')
    assert (bob.recipes_all, bob.recipes_up_to_date, bob.recipes_cant_be_updated,
            bob.percentage_done) == (1, '', 1, '0%')
    # One upgrade each, in the week of UPGRADE_DATE
    assert [n for n in alice.interval_statistics if n] == [2]
    assert [n for n in bob.interval_statistics if n] == [1]
    assert alice.interval_statistics.index(2) == bob.interval_statistics.index(1)


def test_queries_do_not_grow_with_maintainers(client, rrs_plan):
    history = histories(rrs_plan.layerbranch)
    # All 'N', so the plan-wide statistics take the same path both times
    add_recipe(rrs_plan.layerbranch, history, 'recipe-0', 'Maintainer 0', 'N')
    maintainer_list(client)  # fills the per-process caches first
    with CaptureQueriesContext(connection) as one:
        assert 'Maintainer 0' in maintainer_list(client)
    for i in range(1, 6):
        add_recipe(rrs_plan.layerbranch, history, f'recipe-{i}', f'Maintainer {i}', 'N')
    with CaptureQueriesContext(connection) as six:
        assert len(maintainer_list(client)) == 6
    assert len(six) == len(one)
