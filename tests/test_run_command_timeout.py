# layerindex-web - tests for the timeout in run_command_interruptible()
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import logging
import os
import subprocess
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))

from layerindex import utils


def is_running(pid):
    # A killed process that nobody has reaped yet is a zombie, not running.
    # Reading the stat file of a process that goes away after open() gives
    # ESRCH rather than ENOENT.
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except (FileNotFoundError, ProcessLookupError):
        return False


@pytest.mark.parametrize('timeout', [None, 30])
def test_command_that_finishes(timeout):
    assert utils.run_command_interruptible('echo hello', timeout=timeout) == (0, 'hello\n')


def test_command_that_hangs_is_killed_with_its_children():
    # [YOCTO #16508] the shell's child keeps the output pipe open, like the
    # BitBake server under upgrade_history_internal.py did, so only killing
    # the shell would leave this waiting for ever
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as e:
        utils.run_command_interruptible('sleep 60 & echo started $!; wait', timeout=1)
    assert time.monotonic() - start < 15
    assert e.value.output.startswith('started ')
    assert not is_running(int(e.value.output.split()[1]))


def test_upgrade_history_skips_a_commit_that_times_out(monkeypatch, caplog):
    import rrs_upgrade_history

    def hang(cmd, timeout=None):
        assert timeout == 5
        raise subprocess.TimeoutExpired(cmd, timeout)

    # The test settings don't install the rrs app; run_internal() only needs
    # Release for an initial import
    monkeypatch.setitem(sys.modules, 'rrs.models', types.SimpleNamespace(Release=None))
    monkeypatch.setattr(utils, 'runcmd', lambda *args, **kwargs: 'abc123')
    monkeypatch.setattr(utils, 'run_command_interruptible', hang)
    plan_branch = types.SimpleNamespace(python3_switch_date=rrs_upgrade_history.datetime(2016, 6, 2),
                                        python3_environment=None,
                                        layerbranch=types.SimpleNamespace(id=1))
    options = types.SimpleNamespace(commit_timeout=5, filter_files='', dry_run=False, loglevel=logging.INFO)
    with caplog.at_level(logging.ERROR):
        # Returns instead of exiting, so the next commit is analysed
        rrs_upgrade_history.run_internal(plan_branch, 'deadbeef', rrs_upgrade_history.datetime(2026, 2, 27),
                                         options, logging.getLogger('test'), {})
    assert 'deadbeef timed out after 5 seconds' in caplog.text
