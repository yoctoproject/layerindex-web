# layerindex-web - tests for the RRS tools' logger
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import logging
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rrs', 'tools'))
from common import get_logger


@pytest.fixture
def readonly_cwd(tmp_path, monkeypatch):
    os.chmod(tmp_path, 0o555)
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    os.chmod(tmp_path, 0o755)


def test_no_log_file_without_tools_log_dir(readonly_cwd):
    # [YOCTO #16499] the scripts run in a directory they can't write to
    logger = get_logger('RRSTestNoDir', types.SimpleNamespace(TOOLS_LOG_DIR=''))
    assert not [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert os.listdir(readonly_cwd) == []


def test_log_file_in_tools_log_dir(tmp_path):
    logger = get_logger('RRSTestDir', types.SimpleNamespace(TOOLS_LOG_DIR=str(tmp_path)))
    logger.info('hello')
    for h in logger.handlers:
        h.flush()
    assert 'hello' in (tmp_path / 'RRSTestDir').read_text()
