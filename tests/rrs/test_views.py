# layerindex-web - smoke tests for the RRS pages
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-generated, Claude Opus 5.5

import datetime

import pytest

from rrs.models import RecipeSymbol, RecipeUpgrade

PAGES = ['recipes', 'recipesreport', 'maintainers', 'stats']


@pytest.fixture
def busybox(rrs_plan):
    symbol = RecipeSymbol.objects.create(layerbranch=rrs_plan.layerbranch, pn='busybox',
                                         summary='Tiny versions of many common UNIX utilities')
    date = datetime.datetime(2026, 11, 1)  # USE_TZ is False
    RecipeUpgrade.objects.create(recipesymbol=symbol, version='1.37.0', author_date=date,
                                 commit_date=date, upgrade_type='U')
    return symbol


def test_front_page_redirects_to_the_recipe_list(client, rrs_plan):
    response = client.get('/rrs/')
    assert response.status_code == 302
    assert response['Location'].startswith('/rrs/recipes/OE-Core/')


@pytest.mark.parametrize('page', PAGES)
def test_milestone_pages(client, busybox, page):
    response = client.get(f'/rrs/{page}/OE-Core/6.2/M1/')
    assert response.status_code == 200


def test_recipe_list_shows_the_recipe(client, busybox):
    response = client.get('/rrs/recipes/OE-Core/6.2/M1/')
    assert [item.name for item in response.context['recipe_list']] == ['busybox']


def test_recipe_detail(client, busybox):
    response = client.get(f'/rrs/recipedetail/OE-Core/{busybox.pk}/')
    assert response.status_code == 200
    assert b'busybox' in response.content


def test_unknown_milestone_is_404(client, rrs_plan):
    assert client.get('/rrs/recipes/OE-Core/6.2/M9/').status_code == 404
