# layerindex-web - tests for matching recipes to distro packages in rrs/tools/rrs_distros.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))


@pytest.fixture
def rrs_distros(monkeypatch):
    # The test settings don't install the rrs app, which the script imports
    monkeypatch.setitem(sys.modules, 'rrs.models', types.SimpleNamespace(RecipeDistro=None, MaintenancePlan=None))
    monkeypatch.delitem(sys.modules, 'rrs_distros', raising=False)
    import rrs_distros
    return rrs_distros


@pytest.fixture
def pkglst_dir(tmp_path):
    # Package lists as OE-Core's distro_check writes them: <distro>-<release>, "<name>:<section>" lines
    (tmp_path / 'Debian-13.7').write_text('brotli:main\npython3-brotli:main\nlz4:main\nfoo:main\n')
    (tmp_path / 'Fedora-45').write_text('python-brotli:main\nlz4:main\n')
    return tmp_path


def search(rrs_distros, pkglst_dir, pn, alias=None):
    recipe = types.SimpleNamespace(pn=pn)
    data = types.SimpleNamespace(getVar=lambda name, expand=True: alias if name == 'DISTRO_PN_ALIAS' else None)
    return rrs_distros.search_package_in_distros(str(pkglst_dir), recipe, data)


def test_native_suffix_is_ignored(rrs_distros, pkglst_dir):
    assert search(rrs_distros, pkglst_dir, 'foo-native') == {'Debian-main': 'foo'}


def test_distro_pn_alias(rrs_distros, pkglst_dir):
    assert search(rrs_distros, pkglst_dir, 'liblz4', alias='Debian=lz4 Fedora=lz4') == {'Debian-main': 'lz4', 'Fedora-main': 'lz4'}


def test_python3_recipe(rrs_distros, pkglst_dir):
    # [YOCTO #16513] Debian's list has the python3-brotli binary package,
    # Fedora's has the python-brotli source package
    assert search(rrs_distros, pkglst_dir, 'python3-brotli') == {'Debian-main': 'python3-brotli', 'Fedora-main': 'python-brotli'}


def test_python3_recipe_not_matched_by_bare_name(rrs_distros, pkglst_dir):
    # lz4 is the C library, not the Python module
    assert search(rrs_distros, pkglst_dir, 'python3-lz4') == {}
