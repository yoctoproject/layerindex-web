# layerindex-web - tests for the RRS recipe list
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

# The recipe list shows each recipe's patch counts, and must get them without
# running queries per recipe.

import datetime

from django.db import connection
from django.test.utils import CaptureQueriesContext

from layerindex.models import Patch, Recipe
from rrs.models import RecipeSymbol, RecipeUpgrade

URL = '/rrs/recipes/OE-Core/6.2/M1/'


def add_recipe(layerbranch, pn, patch_statuses=(), recipe=True):
    """A recipe that RRS lists for the milestone, with patches of the given statuses"""
    symbol = RecipeSymbol.objects.create(layerbranch=layerbranch, pn=pn, summary=pn)
    date = datetime.datetime(2026, 11, 1)  # USE_TZ is False
    RecipeUpgrade.objects.create(recipesymbol=symbol, version='1.0', author_date=date,
                                 commit_date=date, upgrade_type='U')
    if recipe:
        obj = Recipe.objects.create(layerbranch=layerbranch, filename=f'{pn}_1.0.bb',
                                    filepath='recipes', pn=pn, pv='1.0')
        for i, status in enumerate(patch_statuses):
            Patch.objects.create(recipe=obj, path=f'{pn}-{i}.patch',
                                 src_path=f'{pn}-{i}.patch', status=status)
    return symbol


def recipe_list(client):
    response = client.get(URL)
    assert response.status_code == 200
    return {item.name: item for item in response.context['recipe_list']}


def test_patch_counts(client, rrs_plan):
    layerbranch = rrs_plan.layerbranch
    add_recipe(layerbranch, 'busybox', ['P', 'P', 'A'])
    add_recipe(layerbranch, 'zlib', [])
    add_recipe(layerbranch, 'norecipe', recipe=False)
    # A second recipe with the same pn: the first one by id is counted
    add_recipe(layerbranch, 'gcc', ['P'])
    later = Recipe.objects.create(layerbranch=layerbranch, filename='gcc_2.0.bb',
                                  filepath='recipes', pn='gcc', pv='2.0')
    Patch.objects.create(recipe=later, path='x.patch', src_path='x.patch', status='P')
    Patch.objects.create(recipe=later, path='y.patch', src_path='y.patch', status='P')

    counts = {name: (item.patches_total, item.patches_pending)
              for name, item in recipe_list(client).items()}

    assert counts == {'busybox': (3, 2), 'zlib': (0, 0), 'norecipe': (0, 0), 'gcc': (1, 1)}


def test_queries_do_not_grow_with_recipes(client, rrs_plan):
    add_recipe(rrs_plan.layerbranch, 'recipe-0', ['P'])
    recipe_list(client)  # fills the per-process caches first
    with CaptureQueriesContext(connection) as one:
        assert len(recipe_list(client)) == 1
    for i in range(1, 6):
        add_recipe(rrs_plan.layerbranch, f'recipe-{i}', ['P'])
    with CaptureQueriesContext(connection) as six:
        assert len(recipe_list(client)) == 6
    assert len(six) == len(one)
