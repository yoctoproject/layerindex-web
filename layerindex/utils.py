# Utilities for layerindex-web
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
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

def runcmd(cmd, destdir=None, printerr=True, logger=None):
    """
        execute command, raise CalledProcessError if fail
        return output if succeed
    """
    #logger.debug("run cmd '%s' in %s" % (cmd, os.getcwd() if destdir is None else destdir))
    out = os.tmpfile()
    try:
        subprocess.check_call(cmd, stdout=out, stderr=out, cwd=destdir, shell=True)
    except subprocess.CalledProcessError,e:
        out.seek(0)
        if printerr:
            output = out.read()
            if logger:
                logger.error("%s" % output)
            else:
                sys.stderr.write("%s\n" % output)
        e.output = output
        raise e

    out.seek(0)
    output = out.read()
    #logger.debug("output: %s" % output.rstrip() )
    return output

def setup_django():
    # Get access to our Django model
    newpath = os.path.abspath(os.path.dirname(__file__) + '/..')
    sys.path.append(newpath)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

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
