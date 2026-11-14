# layerindex-web - tests for create_distro_packages_list() in rrs/tools/common.py
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))

import common


def fake_distro_check(fail=False):
    # Like OE-Core's create_socket(): bb.utils.export_proxies() writes the
    # datastore's PATH and HOME into os.environ
    def create_distro_packages_list(fetchdir, d):
        os.environ['PATH'] = '/oe-core/scripts:/build/tmp/hosttools'
        os.environ['HOME'] = '/build'
        os.environ['http_proxy'] = 'http://proxy.example.com:3128'
        if fail:
            raise OSError('HTTP Error 404: Not Found')
    return types.SimpleNamespace(create_distro_packages_list=create_distro_packages_list)


@pytest.mark.parametrize('fail', [False, True])
def test_create_distro_packages_list_keeps_the_environment(monkeypatch, fail):
    # [YOCTO #16506] OE-Core's PATH left in the environment made the next
    # layer branch's git commands run OE-Core's scripts/git without python3
    monkeypatch.setenv('PATH', '/usr/local/bin:/usr/bin:/bin')
    monkeypatch.setenv('HOME', '/home/layers')
    monkeypatch.delenv('http_proxy', raising=False)
    before = dict(os.environ)

    if fail:
        with pytest.raises(OSError):
            common.create_distro_packages_list(fake_distro_check(fail=True), '/fetch', None)
    else:
        common.create_distro_packages_list(fake_distro_check(), '/fetch', None)

    assert dict(os.environ) == before
