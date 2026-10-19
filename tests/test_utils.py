# layerindex-web - tests for layerindex/utils.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import operator
import os
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


def make_layer(path):
    (path / 'conf').mkdir(parents=True)
    (path / 'conf' / 'layer.conf').write_text('')


@pytest.fixture
def repo_with_nested_layers(tmp_path):
    """A repository whose layer (in subdirectory 'meta-top') contains other
    layers, as when layers are vendored with git subtree."""
    repodir = tmp_path / 'repo'
    layerdir = repodir / 'meta-top'
    make_layer(layerdir)
    (layerdir / 'recipes-core' / 'foo').mkdir(parents=True)
    make_layer(layerdir / 'meta-sub')
    make_layer(layerdir / 'meta-openembedded' / 'meta-oe')
    # A directory whose name starts like a nested layer's, but isn't one
    (layerdir / 'meta-subsidiary' / 'recipes-x').mkdir(parents=True)
    return str(repodir), str(layerdir)


def test_nested_layer_dirs(repo_with_nested_layers):
    repodir, layerdir = repo_with_nested_layers
    assert sorted(utils.nested_layer_dirs(layerdir)) == [
        os.path.join(layerdir, 'meta-openembedded', 'meta-oe') + os.sep,
        os.path.join(layerdir, 'meta-sub') + os.sep,
    ]


@pytest.mark.parametrize('path, expected', [
    # Paths relative to the repository, as git diff reports them
    ('meta-top/meta-openembedded/meta-oe/recipes-a/a/a_1.0.bb', True),
    ('meta-top/meta-sub/recipes-b/b/b_1.0.bb', True),
    ('meta-top/recipes-core/foo/foo_1.0.bb', False),
    ('meta-top/meta-subsidiary/recipes-x/x/x_1.0.bb', False),
    ('meta-top/meta-openembedded/README', False),
])
def test_in_nested_layer(repo_with_nested_layers, path, expected):
    repodir, layerdir = repo_with_nested_layers
    nested = utils.nested_layer_dirs(layerdir)
    assert utils.in_nested_layer(path, nested, repodir) is expected
    # Absolute paths give the same answer
    assert utils.in_nested_layer(os.path.join(repodir, path), nested, repodir) is expected
