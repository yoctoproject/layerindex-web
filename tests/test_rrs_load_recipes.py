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
