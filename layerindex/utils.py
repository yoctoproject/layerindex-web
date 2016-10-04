# Utilities for layerindex-web
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import tempfile
import subprocess
import logging
import time
import fcntl

def get_branch(branchname):
    from layerindex.models import Branch
    res = list(Branch.objects.filter(name=branchname)[:1])
    if res:
        return res[0]
    return None

def get_layer(layername):
    from layerindex.models import LayerItem
    res = list(LayerItem.objects.filter(name=layername)[:1])
    if res:
        return res[0]
    return None

def setup_tinfoil(bitbakepath, enable_tracking):
    sys.path.insert(0, bitbakepath + '/lib')
    import bb.tinfoil
    import bb.cooker
    import bb.data
    try:
        tinfoil = bb.tinfoil.Tinfoil(tracking=enable_tracking)
    except TypeError:
        # old API
        tinfoil = bb.tinfoil.Tinfoil()
        if enable_tracking:
            tinfoil.cooker.enableDataTracking()
    tinfoil.prepare(config_only = True)

    return tinfoil

def checkout_layer_branch(layerbranch, repodir, logger=None):

    branchname = layerbranch.branch.name
    if layerbranch.actual_branch:
        branchname = layerbranch.actual_branch

    out = runcmd("git checkout origin/%s" % branchname, repodir, logger=logger)
    out = runcmd("git clean -f -x", repodir, logger=logger)

def is_layer_valid(layerdir):
    conf_file = os.path.join(layerdir, "conf", "layer.conf")
    if not os.path.isfile(conf_file):
        return False
    return True

def parse_layer_conf(layerdir, data, logger=None):
    conf_file = os.path.join(layerdir, "conf", "layer.conf")

    if not is_layer_valid(layerdir):
        if logger:
            logger.error("Cannot find layer.conf: %s"% conf_file)
        return

    data.setVar('LAYERDIR', str(layerdir))
    if hasattr(bb, "cookerdata"):
        # Newer BitBake
        data = bb.cookerdata.parse_config_file(conf_file, data)
    else:
        # Older BitBake (1.18 and below)
        data = bb.cooker._parse(conf_file, data)
    data.expandVarref('LAYERDIR')

def runcmd(cmd, destdir=None, printerr=True, logger=None):
    """
        execute command, raise CalledProcessError if fail
        return output if succeed
    """
    if logger:
        logger.debug("run cmd '%s' in %s" % (cmd, os.getcwd() if destdir is None else destdir))
    out = tempfile.TemporaryFile()
    try:
        subprocess.check_call(cmd, stdout=out, stderr=out, cwd=destdir, shell=True)
    except subprocess.CalledProcessError as e:
        out.seek(0)
        if printerr:
            output = out.read()
            output = output.decode('ascii').strip()
            if logger:
                logger.error("%s" % output)
            else:
                sys.stderr.write("%s\n" % output)
        e.output = output
        raise e

    out.seek(0)
    output = out.read()
    output = output.decode('ascii').strip()
    if logger:
        logger.debug("output: %s" % output.rstrip() )
    return output

def setup_django():
    import django
    # Get access to our Django model
    newpath = os.path.abspath(os.path.dirname(__file__) + '/..')
    sys.path.append(newpath)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
    django.setup()

def logger_create(name):
    logger = logging.getLogger(name)
    loggerhandler = logging.StreamHandler()
    loggerhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(loggerhandler)
    logger.setLevel(logging.INFO)
    return logger

def lock_file(fn):
    starttime = time.time()
    while True:
        lock = open(fn, 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock
        except IOError:
            lock.close()
            if time.time() - starttime > 30:
                return None

def unlock_file(lock):
    fcntl.flock(lock, fcntl.LOCK_UN)
