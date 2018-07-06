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
import signal
import codecs

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

def get_layer_var(config_data, var, logger):
    collection = config_data.getVar('BBFILE_COLLECTIONS', True)
    if collection:
        collection = collection.strip()
        collection_list = collection.split()
        collection = collection_list[0]
        layerdir = config_data.getVar('LAYERDIR', True)
        if len(collection_list) > 1:
            logger.warn('%s: multiple collections found, handling first one (%s) only' % (layerdir, collection))
        if var == 'BBFILE_COLLECTIONS':
            return collection
    value = config_data.getVar('%s_%s' % (var, collection), True)
    if not value:
        value = config_data.getVar(var, True)
    return value or ''

def is_deps_satisfied(req_col, req_ver, collections):
    """ Check whether required collection and version are in collections"""
    for existed_col, existed_ver in collections:
        if req_col == existed_col:
            # If there is no version constraint, return True when collection matches
            if not req_ver:
                return True
            else:
                # If there is no version in the found layer, then don't use this layer.
                if not existed_ver:
                    continue
                (op, dep_version) = req_ver.split()
                success = bb.utils.vercmp_string_op(existed_ver, dep_version, op)
                if success:
                    return True
    # Return False when not found
    return False

def get_dependency_layer(depname, version_str=None, logger=None):
    from layerindex.models import LayerItem, LayerBranch

    # Get any LayerBranch with a layer that has a name that matches depmod, or
    # a LayerBranch that has the collection name depmod.
    res = list(LayerBranch.objects.filter(layer__name=depname)) + \
          list(LayerBranch.objects.filter(collection=depname))

    # Nothing found, return.
    if not res:
        return None

    # If there is no version constraint, return the first one found.
    if not version_str:
        return res[0].layer

    (operator, dep_version) = version_str.split()
    for layerbranch in res:
        layer_ver = layerbranch.version

        # If there is no version in the found layer, then don't use this layer.
        if not layer_ver:
            continue

        try:
            success = bb.utils.vercmp_string_op(layer_ver, version_str, operator)
        except bb.utils.VersionStringException as vse:
            raise vse

        if success:
            return layerbranch.layer

    return None

def add_dependencies(layerbranch, config_data, logger=None):
    _add_dependency("LAYERDEPENDS", 'dependency', layerbranch, config_data, logger=logger)

def add_recommends(layerbranch, config_data, logger=None):
    _add_dependency("LAYERRECOMMENDS", 'recommends', layerbranch, config_data, logger=logger, required=False)

def _add_dependency(var, name, layerbranch, config_data, logger=None, required=True):
    from layerindex.models import LayerBranch, LayerDependency

    layer_name = layerbranch.layer.name
    var_name = layer_name

    if layerbranch.collection:
        var_name = layerbranch.collection


    dep_list = config_data.getVar("%s_%s" % (var, var_name), True)

    if not dep_list:
        return

    try:
        dep_dict = bb.utils.explode_dep_versions2(dep_list)
    except bb.utils.VersionStringException as vse:
        logger.debug('Error parsing %s_%s for %s\n%s' % (var, var_name, layer_name, str(vse)))
        return

    need_remove = LayerDependency.objects.filter(layerbranch=layerbranch).filter(required=required)
    for dep, ver_list in list(dep_dict.items()):
        ver_str = None
        if ver_list:
            ver_str = ver_list[0]

        try:
            dep_layer = get_dependency_layer(dep, ver_str, logger)
        except bb.utils.VersionStringException as vse:
            if logger:
                logger.error('Error getting %s %s for %s\n%s' %(name, dep. layer_name, str(vse)))
            continue

        # No layer found.
        if not dep_layer:
            if logger:
                logger.error('Cannot resolve %s %s (version %s) for %s' % (name, dep, ver_str, layer_name))
                continue

        # Preparing to remove obsolete ones
        if need_remove:
            need_remove = need_remove.exclude(dependency=dep_layer)

        # Skip existing entries.
        existing = list(LayerDependency.objects.filter(layerbranch=layerbranch).filter(required=required).filter(dependency=dep_layer))
        if existing:
            logger.debug('Skipping %s - already a dependency for %s' % (dep, layer_name))
            continue

        if logger:
            logger.debug('Adding %s %s to %s' % (name, dep_layer.name, layer_name))

        layerdep = LayerDependency()
        layerdep.layerbranch = layerbranch
        layerdep.dependency = dep_layer
        layerdep.required = required
        layerdep.save()

    if need_remove:
        import settings
        remove_layer_dependencies = getattr(settings, 'REMOVE_LAYER_DEPENDENCIES', False)
        if remove_layer_dependencies:
            logger.info('Removing obsolete dependencies "%s" for layer %s' % (need_remove, layer_name))
            need_remove.delete()
        else:
            logger.warn('Dependencies "%s" are not in %s\'s conf/layer.conf' % (need_remove, layer_name))
            logger.warn('Either set REMOVE_LAYER_DEPENDENCIES to remove them from the database, or fix conf/layer.conf')

def set_layerbranch_collection_version(layerbranch, config_data, logger=None):
    layerbranch.collection = config_data.getVar('BBFILE_COLLECTIONS', True)
    ver_str = "LAYERVERSION_"
    if layerbranch.collection:
        layerbranch.collection = layerbranch.collection.strip()
        ver_str += layerbranch.collection
        layerbranch.version = config_data.getVar(ver_str, True)

def setup_tinfoil(bitbakepath, enable_tracking, loglevel=None):
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
    tinfoil.logger.setLevel(logging.WARNING)
    if loglevel:
        tinfoil.logger.setLevel(loglevel)
    tinfoil.prepare(config_only = True)

    return tinfoil

def explode_dep_versions2(bitbakepath, deps):
    bblib = bitbakepath + '/lib'
    if not bblib in sys.path:
        sys.path.insert(0, bblib)
    import bb.utils
    return bb.utils.explode_dep_versions2(deps)

def checkout_repo(repodir, commit, logger, force=False):
    """
    Check out a revision in a repository, ensuring that untracked/uncommitted
    files don't get in the way.
    WARNING: this will throw away any untracked/uncommitted files in the repo,
    so it is only suitable for use with repos where you don't care about such
    things (which we don't for the layer repos that we use)
    """
    if force:
        currentref = ''
    else:
        try:
            # The "git rev-parse HEAD" returns "fatal: ambiguous argument 'HEAD'"
            # when a repo is unable to check out after git clone:
            # git clone <url>
            # warning: remote HEAD refers to nonexistent ref, unable to checkout.
            # So check and avoid that
            currentref = runcmd("git rev-parse HEAD", repodir, logger=logger).strip()
        except Exception as esc:
            logger.warn(esc)
            currentref = ''
    if currentref != commit:
        # Reset in case there are added but uncommitted changes
        runcmd("git reset --hard", repodir, logger=logger)
        # Drop any untracked files in case these cause problems (either because
        # they will exist in the revision we're checking out, or will otherwise
        # interfere with operation, e.g. stale pyc files)
        runcmd("git clean -qdfx", repodir, logger=logger)
        # Now check out the revision
        runcmd("git checkout %s" % commit, repodir, logger=logger)

def checkout_layer_branch(layerbranch, repodir, logger=None):
    branchname = layerbranch.branch.name
    if layerbranch.actual_branch:
        branchname = layerbranch.actual_branch
    checkout_repo(repodir, 'origin/%s' % branchname, logger)

def is_layer_valid(layerdir):
    conf_file = os.path.join(layerdir, "conf", "layer.conf")
    if not os.path.isfile(conf_file):
        return False
    return True

def is_branch_valid(layerdir, branch):
    import git

    g = git.cmd.Git(layerdir)
    assert g.rev_parse('--is-bare-repository') == 'false'
    try:
        g.rev_parse('--verify', 'origin/%s' % branch)
    except git.exc.GitCommandError:
        return False
    return True

def parse_conf(conf_file, d):
    if hasattr(bb.parse, "handle"):
        # Newer BitBake
        data = bb.parse.handle(conf_file, d, include=True)
    else:
        # Older BitBake (1.18 and below)
        data = bb.cooker._parse(conf_file, d)
    return data

def parse_layer_conf(layerdir, data, logger=None):
    conf_file = os.path.join(layerdir, "conf", "layer.conf")

    if not is_layer_valid(layerdir):
        if logger:
            logger.error("Cannot find layer.conf: %s"% conf_file)
        return

    data.setVar('LAYERDIR', str(layerdir))
    data = parse_conf(conf_file, data)
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
        output = out.read()
        output = output.decode('utf-8', errors='replace').strip()
        if printerr:
            if logger:
                logger.error("%s" % output)
            else:
                sys.stderr.write("%s\n" % output)
        e.output = output
        raise e

    out.seek(0)
    output = out.read()
    output = output.decode('utf-8', errors='replace').strip()
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

class ListHandler(logging.Handler):
    """Logging handler which accumulates formatted log records in a list, returning the list on demand"""
    def __init__(self):
        self.log = []
        logging.Handler.__init__(self, logging.WARNING)
    def emit(self, record):
        self.log.append('%s\n' % self.format(record))
    def read(self):
        log = self.log
        self.log = []
        return log


def lock_file(fn, timeout=30, logger=None):
    start = time.time()
    last = start
    counter = 1
    while True:
        lock = open(fn, 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock
        except IOError:
            lock.close()
            current = time.time()
            if current - start > timeout:
                return None
            # Print a message in every 5 seconds
            if logger and (current - last > 5):
                last = current
                logger.info('Trying to get lock on %s (tried %s seconds) ...' % (fn, (5 * counter)))
                counter += 1

def unlock_file(lock):
    fcntl.flock(lock, fcntl.LOCK_UN)

def chain_unique(*iterables):
    """Chain unique objects in a list of querysets, preserving order"""
    seen = set()
    for element in iterables:
        for item in element:
            k = item.id
            if k not in seen:
                seen.add(k)
                yield item

def setup_core_layer_sys_path(settings, branchname):
    """
    Add OE-Core's lib/oe directory to sys.path in order to allow importing
    OE python modules
    """
    core_layer = get_layer(settings.CORE_LAYER_NAME)
    core_layerbranch = core_layer.get_layerbranch(branchname)
    if core_layerbranch:
        core_urldir = core_layer.get_fetch_dir()
        core_repodir = os.path.join(settings.LAYER_FETCH_DIR, core_urldir)
        core_layerdir = os.path.join(core_repodir, core_layerbranch.vcs_subdir)
        sys.path.insert(0, os.path.join(core_layerdir, 'lib'))

def run_command_interruptible(cmd):
    """
    Run a command with output displayed on the console, but ensure any Ctrl+C is
    processed only by the child process.
    """
    def reenable_sigint():
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        process = subprocess.Popen(
            cmd, cwd=os.path.dirname(sys.argv[0]), shell=True, preexec_fn=reenable_sigint, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        reader = codecs.getreader('utf-8')(process.stdout, errors='surrogateescape')
        buf = ''
        while True:
            out = reader.read(1, 1)
            if out:
                sys.stdout.write(out)
                sys.stdout.flush()
                buf += out
            elif out == '' and process.poll() != None:
                break

    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    return process.returncode, buf
