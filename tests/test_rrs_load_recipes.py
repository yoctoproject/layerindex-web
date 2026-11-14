# layerindex-web - tests for load_recipes() in rrs/tools/common.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))


def test_load_recipes_checks_out_bitbake_before_importing_it(monkeypatch):
    # [YOCTO #16501] bb must come from the revision init_parser() checks out
    import common
    # As common_setup() does for the scripts: recipeparse imports utils
    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'layerindex'))
    from layerindex import recipeparse

    class Stop(Exception):
        pass

    def fake_init_parser(*args, **kwargs):
        assert 'bb.fetch' not in sys.modules
        raise Stop()

    for name in [m for m in sys.modules if m == 'bb' or m.startswith('bb.')]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(recipeparse, 'init_parser', fake_init_parser)
    with pytest.raises(Stop):
        common.load_recipes(types.SimpleNamespace(branch=None), '/nonexistent', '/nonexistent',
                            types.SimpleNamespace(), None)


@pytest.mark.django_db
@pytest.mark.parametrize('nocheckout', [False, True])
def test_load_recipes_checks_out_the_layer_branch(monkeypatch, nocheckout):
    # [YOCTO #16502] parse the branch being worked on, not whichever branch
    # the repositories were left on
    import common
    monkeypatch.syspath_prepend(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'layerindex'))
    from layerindex import recipeparse, utils
    from layerindex.models import Branch, LayerBranch, LayerDependency, LayerItem

    master, _ = Branch.objects.get_or_create(name='master', defaults={'bitbake_branch': 'master'})
    layers = {}
    for name in ('meta-oe', 'meta-python'):
        layer = LayerItem.objects.create(name=name, status='P', layer_type='A', summary=name,
                                         description=name, vcs_url='git://example.com/%s.git' % name)
        layers[name] = LayerBranch.objects.create(layer=layer, branch=master, actual_branch='main')
    LayerDependency.objects.create(layerbranch=layers['meta-oe'], dependency=layers['meta-python'].layer)

    class Stop(Exception):
        pass

    def fake_setup_layer(*args, **kwargs):
        raise Stop()

    # load_recipes() imports bb.fetch once init_parser() has checked out BitBake
    bb = types.ModuleType('bb')
    bb.fetch = types.ModuleType('bb.fetch')
    bb.fetch.FetchError = Exception
    monkeypatch.setitem(sys.modules, 'bb', bb)
    monkeypatch.setitem(sys.modules, 'bb.fetch', bb.fetch)

    checkouts = []
    monkeypatch.setattr(recipeparse, 'init_parser', lambda *args, **kwargs: (types.SimpleNamespace(config_data=None), '/tmp'))
    monkeypatch.setattr(recipeparse, 'setup_layer', fake_setup_layer)
    monkeypatch.setattr(utils, 'checkout_repo', lambda repodir, ref, logger=None: checkouts.append((os.path.basename(repodir), ref)))
    with pytest.raises(Stop):
        common.load_recipes(layers['meta-oe'], '/bitbake', '/fetch', types.SimpleNamespace(), None,
                            recipe_files=[], nocheckout=nocheckout)
    if nocheckout:
        assert checkouts == []
    else:
        assert checkouts == [('git___example_com_meta-oe_git', 'origin/main'),
                             ('git___example_com_meta-python_git', 'origin/main')]
