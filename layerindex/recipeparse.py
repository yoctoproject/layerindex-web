# Utility functions for parsing recipes using bitbake within layerindex-web
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import os.path
import utils
import tempfile
import re
import fnmatch

class RecipeParseError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

def _setup_tinfoil(bitbakepath, enable_tracking):
    sys.path.insert(0, bitbakepath + '/lib')
    import bb.tinfoil
    import bb.cooker
    import bb.data
    tinfoil = bb.tinfoil.Tinfoil()
    if enable_tracking:
        tinfoil.cooker.enableDataTracking()
    tinfoil.prepare(config_only = True)

    return tinfoil

def _parse_layer_conf(layerdir, data):
    data.setVar('LAYERDIR', str(layerdir))
    if hasattr(bb, "cookerdata"):
        # Newer BitBake
        data = bb.cookerdata.parse_config_file(os.path.join(layerdir, "conf", "layer.conf"), data)
    else:
        # Older BitBake (1.18 and below)
        data = bb.cooker._parse(os.path.join(layerdir, "conf", "layer.conf"), data)
    data.expandVarref('LAYERDIR')


def init_parser(settings, branch, bitbakepath, enable_tracking=False, nocheckout=False, classic=False, logger=None):
    if not (nocheckout or classic):
        # Check out the branch of BitBake appropriate for this branch and clean out any stale files (e.g. *.pyc)
        out = utils.runcmd("git checkout origin/%s" % branch.bitbake_branch, bitbakepath, logger=logger)
        out = utils.runcmd("git clean -f -x", bitbakepath, logger=logger)

    # Skip sanity checks
    os.environ['BB_ENV_EXTRAWHITE'] = 'DISABLE_SANITY_CHECKS'
    os.environ['DISABLE_SANITY_CHECKS'] = '1'

    fetchdir = settings.LAYER_FETCH_DIR

    if not classic:
        # Ensure we have OE-Core set up to get some base configuration
        core_layer = utils.get_layer(settings.CORE_LAYER_NAME)
        if not core_layer:
            raise RecipeParseError("Unable to find core layer %s in database; check CORE_LAYER_NAME setting" % settings.CORE_LAYER_NAME)
        core_layerbranch = core_layer.get_layerbranch(branch.name)
        core_branchname = branch.name
        if core_layerbranch:
            core_subdir = core_layerbranch.vcs_subdir
            if core_layerbranch.actual_branch:
                core_branchname = core_layerbranch.actual_branch
        else:
            core_subdir = 'meta'
        core_urldir = core_layer.get_fetch_dir()
        core_repodir = os.path.join(fetchdir, core_urldir)
        core_layerdir = os.path.join(core_repodir, core_subdir)
        if not nocheckout:
            out = utils.runcmd("git checkout origin/%s" % core_branchname, core_repodir, logger=logger)
            out = utils.runcmd("git clean -f -x", core_repodir, logger=logger)
        # The directory above where this script exists should contain our conf/layer.conf,
        # so add it to BBPATH along with the core layer directory
        confparentdir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        os.environ['BBPATH'] = str("%s:%s" % (confparentdir, core_layerdir))

    # Change into a temporary directory so we don't write the cache and other files to the current dir
    if not os.path.exists(settings.TEMP_BASE_DIR):
        os.makedirs(settings.TEMP_BASE_DIR)
    tempdir = tempfile.mkdtemp(dir=settings.TEMP_BASE_DIR)
    os.chdir(tempdir)

    tinfoil = _setup_tinfoil(bitbakepath, enable_tracking)

    # Ensure TMPDIR exists (or insane.bbclass will blow up trying to write to the QA log)
    oe_tmpdir = tinfoil.config_data.getVar('TMPDIR', True)
    if not os.path.exists(oe_tmpdir):
        os.makedirs(oe_tmpdir)

    return (tinfoil, tempdir)

def checkout_layer_branch(layerbranch, repodir, logger=None):
    if layerbranch.actual_branch:
        branchname = layerbranch.actual_branch
    else:
        branchname = layerbranch.branch.name
    out = utils.runcmd("git checkout origin/%s" % branchname, repodir, logger=logger)
    out = utils.runcmd("git clean -f -x", repodir, logger=logger)

def setup_layer(config_data, fetchdir, layerdir, layer, layerbranch):
    # Parse layer.conf files for this layer and its dependencies
    # This is necessary not just because BBPATH needs to be set in order
    # for include/require/inherit to work outside of the current directory
    # or across layers, but also because custom variable values might be
    # set in layer.conf.
    config_data_copy = bb.data.createCopy(config_data)
    _parse_layer_conf(layerdir, config_data_copy)
    for dep in layerbranch.dependencies_set.all():
        depurldir = dep.dependency.get_fetch_dir()
        deprepodir = os.path.join(fetchdir, depurldir)
        deplayerbranch = dep.dependency.get_layerbranch(layerbranch.branch.name)
        if not deplayerbranch:
            raise RecipeParseError('Dependency %s of layer %s does not have branch record for branch %s' % (dep.dependency.name, layer.name, layerbranch.branch.name))
        deplayerdir = os.path.join(deprepodir, deplayerbranch.vcs_subdir)
        _parse_layer_conf(deplayerdir, config_data_copy)
    config_data_copy.delVar('LAYERDIR')
    return config_data_copy

def get_var_files(fn, varlist, d):
    import bb.cache
    varfiles = {}
    envdata = bb.cache.Cache.loadDataFull(fn, [], d)
    for v in varlist:
        history = envdata.varhistory.get_variable_files(v)
        if history:
            actualfile = history[-1]
        else:
            actualfile = None
        varfiles[v] = actualfile

    return varfiles

machine_conf_re = re.compile(r'conf/machine/([^/.]*).conf$')
bbclass_re = re.compile(r'classes/([^/.]*).bbclass$')
def detect_file_type(path, subdir_start):
    typename = None
    if fnmatch.fnmatch(path, "*.bb"):
        typename = 'recipe'
    elif fnmatch.fnmatch(path, "*.bbappend"):
        typename = 'bbappend'
    else:
        # Check if it's a machine conf file
        subpath = path[len(subdir_start):]
        res = machine_conf_re.match(subpath)
        if res:
            typename = 'machine'
            return (typename, None, res.group(1))
        else:
            res = bbclass_re.match(subpath)
            if res:
                typename = 'bbclass'
                return (typename, None, res.group(1))

    if typename == 'recipe' or typename == 'bbappend':
        if subdir_start:
            filepath = os.path.relpath(os.path.dirname(path), subdir_start)
        else:
            filepath = os.path.dirname(path)
        return (typename, filepath, os.path.basename(path))

    return (None, None, None)

