#!/usr/bin/env python3

# Fetch layer repositories and update layer index database
#
# Copyright (C) 2013-2016 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import optparse
import codecs
import logging
import subprocess
import signal
from datetime import datetime, timedelta
from distutils.version import LooseVersion
import utils

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = utils.logger_create('LayerIndexUpdate')

# Ensure PythonGit is installed (buildhistory_analysis needs it)
try:
    import git
except ImportError:
    logger.error("Please install PythonGit 0.3.1 or later in order to use this script")
    sys.exit(1)


def reenable_sigint():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

def run_command_interruptible(cmd):
    """
    Run a command with output displayed on the console, but ensure any Ctrl+C is
    processed only by the child process.
    """
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


def prepare_update_layer_command(options, branch, layer, updatedeps=False):
    """Prepare the update_layer.py command line"""
    if branch.update_environment:
        cmdprefix = branch.update_environment.get_command()
    else:
        cmdprefix = 'python3'
    cmd = '%s update_layer.py -l %s -b %s' % (cmdprefix, layer.name, branch.name)
    if updatedeps:
        cmd += ' --update-dependencies'
    if options.reload:
        cmd += ' --reload'
    if options.fullreload:
        cmd += ' --fullreload'
    if options.nocheckout:
        cmd += ' --nocheckout'
    if options.dryrun:
        cmd += ' -n'
    if options.loglevel == logging.DEBUG:
        cmd += ' -d'
    elif options.loglevel == logging.ERROR:
        cmd += ' -q'
    return cmd

def update_actual_branch(layerquery, fetchdir, branch, options, update_bitbake, bitbakepath):
    """Update actual branch for layers and bitbake in database"""
    to_save = set()
    actual_branch = options.actual_branch
    if update_bitbake:
        branchobj = utils.get_branch(branch)
        if actual_branch != branchobj.bitbake_branch:
            if utils.is_branch_valid(bitbakepath, actual_branch):
                logger.info("bitbake: %s.bitbake_branch: %s -> %s" % (branch, branchobj.bitbake_branch, actual_branch))
                branchobj.bitbake_branch = actual_branch
                to_save.add(branchobj)
            else:
                logger.info("Skipping update bitbake_branch for bitbake - branch %s doesn't exist" % actual_branch)
        else:
            logger.info("bitbake: %s.bitbake_branch is already %s, so no change" % (branch, actual_branch))

    for layer in layerquery:
        urldir = layer.get_fetch_dir()
        repodir = os.path.join(fetchdir, urldir)
        if not utils.is_branch_valid(repodir, actual_branch):
            logger.info("Skipping update actual_branch for %s - branch %s doesn't exist" % (layer.name, actual_branch))
            continue
        layerbranch = layer.get_layerbranch(branch)
        if not layerbranch:
            logger.info("Skipping update actual_branch for %s - layerbranch %s doesn't exist" % (layer.name, branch))
            continue
        if actual_branch != layerbranch.actual_branch:
            logger.info("%s: %s.actual_branch: %s -> %s" % (layer.name, branch, layerbranch.actual_branch, actual_branch))
            layerbranch.actual_branch = actual_branch
            to_save.add(layerbranch)
        else:
            logger.info("%s: %s.actual_branch is already %s, so no change" % (layer.name, branch, actual_branch))

    # At last, do the save
    if not options.dryrun:
        for s in to_save:
            s.save()

def main():
    if LooseVersion(git.__version__) < '0.3.1':
        logger.error("Version of GitPython is too old, please install GitPython (python-git) 0.3.1 or later in order to use this script")
        sys.exit(1)


    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-b", "--branch",
            help = "Specify branch(es) to update (use commas to separate multiple). Default is all enabled branches.",
            action="store", dest="branch", default='')
    parser.add_option("-l", "--layer",
            help = "Specify layers to update (use commas to separate multiple). Default is all published layers.",
            action="store", dest="layers")
    parser.add_option("-r", "--reload",
            help = "Reload recipe data instead of updating since last update",
            action="store_true", dest="reload")
    parser.add_option("", "--fullreload",
            help = "Discard existing recipe data and fetch it from scratch",
            action="store_true", dest="fullreload")
    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("-x", "--nofetch",
            help = "Don't fetch repositories",
            action="store_true", dest="nofetch")
    parser.add_option("", "--nocheckout",
            help = "Don't check out branches",
            action="store_true", dest="nocheckout")
    parser.add_option("-a", "--actual-branch",
            help = "Update actual branch for layer and bitbake",
            action="store", dest="actual_branch", default='')
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")

    options, args = parser.parse_args(sys.argv)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)

    utils.setup_django()
    import settings
    from layerindex.models import Branch, LayerItem, Update, LayerUpdate

    logger.setLevel(options.loglevel)

    if options.branch:
        branches = options.branch.split(',')
        for branch in branches:
            if not utils.get_branch(branch):
                logger.error("Specified branch %s is not valid" % branch)
                sys.exit(1)
    else:
        branchquery = Branch.objects.filter(updates_enabled=True)
        branches = [branch.name for branch in branchquery]

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    # For -a option to update bitbake branch
    update_bitbake = False
    if options.layers:
        layers = options.layers.split(',')
        if 'bitbake' in layers:
            update_bitbake = True
            layers.remove('bitbake')
        for layer in layers:
            layerquery = LayerItem.objects.filter(classic=False).filter(name=layer)
            if layerquery.count() == 0:
                logger.error('No layers matching specified query "%s"' % layer)
                sys.exit(1)
        layerquery = LayerItem.objects.filter(classic=False).filter(name__in=layers)
    else:
        # We deliberately exclude status == 'X' ("no update") here
        layerquery = LayerItem.objects.filter(classic=False).filter(status='P')
        if layerquery.count() == 0:
            logger.info("No published layers to update")
            sys.exit(1)
        update_bitbake = True

    if options.actual_branch:
        if not options.branch:
            logger.error("-a option requires -b")
            sys.exit(1)
        elif len(branches) != 1:
            logger.error("Only one branch should be used with -a")
            sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)
    fetchedrepos = []
    failedrepos = {}

    listhandler = utils.ListHandler()
    listhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(listhandler)

    update = Update()
    update.started = datetime.now()
    if options.fullreload or options.reload:
        update.reload = True
    else:
        update.reload = False
    if not options.dryrun:
        update.save()
    try:
        lockfn = os.path.join(fetchdir, "layerindex.lock")
        lockfile = utils.lock_file(lockfn)
        if not lockfile:
            logger.error("Layer index lock timeout expired")
            sys.exit(1)
        try:
            bitbakepath = os.path.join(fetchdir, 'bitbake')

            if not options.nofetch:
                # Fetch latest metadata from repositories
                for layer in layerquery:
                    # Handle multiple layers in a single repo
                    urldir = layer.get_fetch_dir()
                    repodir = os.path.join(fetchdir, urldir)
                    if not (layer.vcs_url in fetchedrepos or layer.vcs_url in failedrepos):
                        logger.info("Fetching remote repository %s" % layer.vcs_url)
                        out = None
                        try:
                            if not os.path.exists(repodir):
                                out = utils.runcmd("git clone %s %s" % (layer.vcs_url, urldir), fetchdir, logger=logger, printerr=False)
                            else:
                                out = utils.runcmd("git fetch", repodir, logger=logger, printerr=False)
                        except subprocess.CalledProcessError as e:
                            logger.error("Fetch of layer %s failed: %s" % (layer.name, e.output))
                            failedrepos[layer.vcs_url] = e.output
                            continue
                        fetchedrepos.append(layer.vcs_url)

                if not (fetchedrepos or update_bitbake):
                    logger.error("No repositories could be fetched, exiting")
                    sys.exit(1)

                logger.info("Fetching bitbake from remote repository %s" % settings.BITBAKE_REPO_URL)
                if not os.path.exists(bitbakepath):
                    out = utils.runcmd("git clone %s %s" % (settings.BITBAKE_REPO_URL, 'bitbake'), fetchdir, logger=logger)
                else:
                    out = utils.runcmd("git fetch", bitbakepath, logger=logger)

            if options.actual_branch:
                update_actual_branch(layerquery, fetchdir, branches[0], options, update_bitbake, bitbakepath)
                return

            # Process and extract data from each layer
            # We now do this by calling out to a separate script; doing otherwise turned out to be
            # unreliable due to leaking memory (we're using bitbake internals in a manner in which
            # they never get used during normal operation).
            last_rev = {}
            for branch in branches:
                branchobj = utils.get_branch(branch)
                for layer in layerquery:
                    layerupdate = LayerUpdate()
                    layerupdate.update = update

                    errmsg = failedrepos.get(layer.vcs_url, '')
                    if errmsg:
                        logger.info("Skipping update of layer %s as fetch of repository %s failed:\n%s" % (layer.name, layer.vcs_url, errmsg))
                        layerbranch = layer.get_layerbranch(branch)
                        if layerbranch:
                            layerupdate.layerbranch = layerbranch
                            layerupdate.started = datetime.now()
                            layerupdate.finished = datetime.now()
                            layerupdate.log = 'ERROR: fetch failed: %s' % errmsg
                            if not options.dryrun:
                                layerupdate.save()
                        continue

                    urldir = layer.get_fetch_dir()
                    repodir = os.path.join(fetchdir, urldir)

                    cmd = prepare_update_layer_command(options, branchobj, layer)
                    logger.debug('Running layer update command: %s' % cmd)
                    layerupdate.started = datetime.now()
                    ret, output = run_command_interruptible(cmd)
                    layerupdate.finished = datetime.now()

                    # We need to get layerbranch here because it might not have existed until
                    # layer_update.py created it, but it still may not create one (e.g. if subdir
                    # didn't exist) so we still need to check
                    layerbranch = layer.get_layerbranch(branch)
                    if layerbranch:
                        last_rev[layerbranch] = layerbranch.vcs_last_rev
                        layerupdate.layerbranch = layerbranch
                        layerupdate.log = output
                        if not options.dryrun:
                            layerupdate.save()

                    if ret == 254:
                        # Interrupted by user, break out of loop
                        break

            # Since update_layer may not be called in the correct order to have the
            # dependencies created before trying to link them, we now have to loop
            # back through all the branches and layers and try to link in the
            # dependencies that may have been missed.  Note that creating the
            # dependencies is a best-effort and continues if they are not found.
            for branch in branches:
                branchobj = utils.get_branch(branch)
                for layer in layerquery:
                    layerbranch = layer.get_layerbranch(branch)
                    if layerbranch:
                        if not (options.reload or options.fullreload):
                            # Skip layers that did not change.
                            layer_last_rev = last_rev.get(layerbranch, None)
                            if layer_last_rev is None or layer_last_rev == layerbranch.vcs_last_rev:
                                continue

                        logger.info('Updating layer dependencies for %s on branch %s' % (layer.name, branch))
                        cmd = prepare_update_layer_command(options, branchobj, layer, updatedeps=True)
                        logger.debug('Running update dependencies command: %s' % cmd)
                        ret, output = run_command_interruptible(cmd)
                        if ret == 254:
                            # Interrupted by user, break out of loop
                            break

        finally:
            utils.unlock_file(lockfile)

    finally:
        update.log = ''.join(listhandler.read())
        update.finished = datetime.now()
        if not options.dryrun:
            update.save()

    if not options.dryrun:
        # Purge old update records
        update_purge_days = getattr(settings, 'UPDATE_PURGE_DAYS', 30)
        Update.objects.filter(started__lte=datetime.now()-timedelta(days=update_purge_days)).delete()

    sys.exit(0)


if __name__ == "__main__":
    main()
