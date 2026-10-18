# layerindex-web - tests for layerindex/utils.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import operator
import sys
import types

import pytest

from layerindex import utils


@pytest.fixture
def fake_bb(monkeypatch):
    """A stand-in for BitBake's bb.utils, which update.py imports from the
    BitBake checkout at runtime. Versions here are plain integers."""
    ops = {'>=': operator.ge, '>': operator.gt, '=': operator.eq, '<=': operator.le, '<': operator.lt}
    bb = types.ModuleType('bb')
    bb.utils = types.ModuleType('bb.utils')
    bb.utils.vercmp_string_op = lambda a, b, op: ops[op](int(a), int(b))
    monkeypatch.setitem(sys.modules, 'bb', bb)
    monkeypatch.setitem(sys.modules, 'bb.utils', bb.utils)


@pytest.mark.parametrize('req_ver, collections, expected', [
    # No version constraint: any matching collection will do
    (None, {('core', '15')}, True),
    (None, {('core', '')}, True),
    # Versioned constraint against the collection's LAYERVERSION
    ('>= 12', {('core', '15')}, True),
    ('>= 16', {('core', '15')}, False),
    ('= 15', {('core', '15')}, True),
    # A collection without a version can't satisfy a versioned constraint
    ('>= 12', {('core', '')}, False),
    # Other collections don't count
    ('>= 12', {('other', '15')}, False),
])
def test_is_deps_satisfied(fake_bb, req_ver, collections, expected):
    assert utils.is_deps_satisfied('core', req_ver, collections) is expected
