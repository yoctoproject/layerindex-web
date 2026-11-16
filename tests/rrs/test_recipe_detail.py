# layerindex-web - tests for the RRS recipe detail page
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# The recipe detail page lists a recipe's upgrades with the release and
# milestone each falls in, and whether its author maintained the recipe then.
# It must get them without running queries per upgrade.

import datetime

from django.db import connection
from django.test.utils import CaptureQueriesContext

from rrs.models import (
    Maintainer,
    RecipeMaintainer,
    RecipeMaintainerHistory,
    RecipeSymbol,
    RecipeUpgrade,
)


def setup_recipe(layerbranch):
    """busybox, maintained by Alice since 2026-10-15"""
    alice, _ = Maintainer.objects.get_or_create(name='Alice')
    Maintainer.objects.get_or_create(name='Bob')
    history = RecipeMaintainerHistory.objects.create(
        title='Update maintainers', date=datetime.datetime(2026, 10, 15), author=alice,
        sha1='0' * 40, layerbranch=layerbranch)
    symbol = RecipeSymbol.objects.create(layerbranch=layerbranch, pn='busybox', summary='busybox')
    RecipeMaintainer.objects.create(recipesymbol=symbol, maintainer=alice, history=history)
    return symbol


def add_upgrade(symbol, version, when, maintainer_name):
    # USE_TZ is False
    RecipeUpgrade.objects.create(recipesymbol=symbol, version=version, author_date=when,
                                 commit_date=when, upgrade_type='U', sha1='1' * 40,
                                 maintainer=Maintainer.objects.get(name=maintainer_name))


def details(client, symbol):
    response = client.get(f'/rrs/recipedetail/OE-Core/{symbol.pk}/')
    assert response.status_code == 200
    return response.context['recipe_upgrade_details']


def test_release_milestone_and_maintainer(client, rrs_plan):
    symbol = setup_recipe(rrs_plan.layerbranch)
    add_upgrade(symbol, '1.37.0', datetime.datetime(2026, 11, 1, 10), 'Alice')
    add_upgrade(symbol, '1.36.1', datetime.datetime(2026, 10, 2, 10), 'Bob')
    # In release 6.2 but after its only milestone
    add_upgrade(symbol, '1.38.0', datetime.datetime(2027, 2, 1, 10), 'Alice')
    # Before any release
    add_upgrade(symbol, '1.30.0', datetime.datetime(2025, 1, 1, 10), 'Alice')

    rows = {d.version: (d.release_name, d.milestone_name, d.maintainer_name, d.is_recipe_maintainer)
            for d in details(client, symbol)}

    assert rows == {
        '1.38.0': ('6.2', '', 'Alice', False),
        '1.37.0': ('6.2', 'M1', 'Alice', True),
        '1.36.1': ('6.2', 'M1', 'Bob', False),
        '1.30.0': ('', '', 'Alice', False),
    }


def test_queries_do_not_grow_with_upgrades(client, rrs_plan):
    symbol = setup_recipe(rrs_plan.layerbranch)
    add_upgrade(symbol, '1.0', datetime.datetime(2026, 10, 2), 'Alice')
    add_upgrade(symbol, '1.1', datetime.datetime(2026, 10, 3), 'Bob')
    details(client, symbol)  # fills the per-process caches first
    with CaptureQueriesContext(connection) as two:
        assert len(details(client, symbol)) == 2
    for day in range(4, 10):
        add_upgrade(symbol, f'1.{day - 2}', datetime.datetime(2026, 10, day),
                    'Alice' if day % 2 else 'Bob')
    with CaptureQueriesContext(connection) as eight:
        assert len(details(client, symbol)) == 8
    assert len(eight) == len(two)
