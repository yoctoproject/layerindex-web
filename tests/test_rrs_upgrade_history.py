# layerindex-web - tests for the BitBake revision rrs_upgrade_history.py uses
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import logging
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))

NEW = '3b9d7bea915dc7f10e845854f1dae325743f9456'   # changed the addfragments syntax
OLD = '378db0fdd95f8704fccd852452555bfddcad384d'   # the revision before it
SWITCH = datetime(2025, 6, 20, 11, 3, 34, tzinfo=timezone.utc)


def local(dt):
    # The script works with naive local times (datetime.fromtimestamp())
    return datetime.fromtimestamp(dt.timestamp())


@pytest.mark.parametrize('commitdate, expected', [
    # [YOCTO #16500] OE-Core commits before it switched need the old revision
    (local(datetime(2025, 6, 19, 10, 5, 42, tzinfo=timezone.utc)), OLD),
    # ... and those from the switch on need the new one
    (local(SWITCH), NEW),
    (local(datetime(2025, 6, 21, 9, 0, 0, tzinfo=timezone.utc)), NEW),
])
def test_bitbake_revision_for_commit(commitdate, expected):
    from rrs_upgrade_history import remapped_bitbake_rev
    bitbake_map = {NEW: (OLD, SWITCH)}
    assert remapped_bitbake_rev(NEW, commitdate, bitbake_map, logging.getLogger('test')) == expected


def test_bitbake_revision_without_limit():
    from rrs_upgrade_history import remapped_bitbake_rev
    log = logging.getLogger('test')
    assert remapped_bitbake_rev('a', datetime(2030, 1, 1), {'a': ('b', None)}, log) == 'b'
    assert remapped_bitbake_rev('c', datetime(2030, 1, 1), {'a': ('b', None)}, log) == 'c'


def run_internal_with(monkeypatch, result):
    import subprocess
    import types
    from layerindex import utils
    import rrs_upgrade_history

    def run(cmd, timeout=None):
        if isinstance(result, Exception):
            raise result
        return result, ''

    # The test settings don't install the rrs app; run_internal() only needs
    # Release for an initial import
    monkeypatch.setitem(sys.modules, 'rrs.models', types.SimpleNamespace(Release=None))
    monkeypatch.setattr(utils, 'runcmd', lambda *args, **kwargs: 'abc123')
    monkeypatch.setattr(utils, 'run_command_interruptible', run)
    plan_branch = types.SimpleNamespace(python3_switch_date=datetime(2016, 6, 2),
                                        python3_environment=None,
                                        layerbranch=types.SimpleNamespace(id=1))
    options = types.SimpleNamespace(commit_timeout=5, filter_files='', dry_run=False, loglevel=logging.INFO)
    return rrs_upgrade_history.run_internal(plan_branch, 'deadbeef', datetime(2026, 2, 27),
                                            options, logging.getLogger('test'), {})


def test_run_internal_success(monkeypatch):
    assert run_internal_with(monkeypatch, 0) is True


def test_run_internal_failure(monkeypatch, caplog):
    # [YOCTO #16515] a failed commit must not be saved as the checkpoint
    with caplog.at_level(logging.ERROR):
        assert run_internal_with(monkeypatch, 1) is False
    assert 'deadbeef failed with exit code 1' in caplog.text


def test_run_internal_timeout_is_skipped(monkeypatch):
    import subprocess
    assert run_internal_with(monkeypatch, subprocess.TimeoutExpired('cmd', 5)) is True
