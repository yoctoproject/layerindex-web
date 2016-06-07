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
import logging
import subprocess
import signal
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
        ret = subprocess.call(cmd, cwd=os.path.dirname(sys.argv[0]), shell=True, preexec_fn=reenable_sigint)
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    return ret


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
    from layerindex.models import Branch, LayerItem

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

    if options.layers:
        layerquery = LayerItem.objects.filter(classic=False).filter(name__in=options.layers.split(','))
        if layerquery.count() == 0:
            logger.error('No layers matching specified query "%s"' % options.layers)
            sys.exit(1)
    else:
        layerquery = LayerItem.objects.filter(classic=False).filter(status='P')
        if layerquery.count() == 0:
            logger.info("No published layers to update")
            sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)
    fetchedrepos = []
    failedrepos = []

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
                            out = utils.runcmd("git clone %s %s" % (layer.vcs_url, urldir), fetchdir, logger=logger)
                        else:
                            out = utils.runcmd("git fetch", repodir, logger=logger)
                    except Exception as e:
                        logger.error("Fetch of layer %s failed: %s" % (layer.name, str(e)))
                        failedrepos.append(layer.vcs_url)
                        continue
                    fetchedrepos.append(layer.vcs_url)

            if not fetchedrepos:
                logger.error("No repositories could be fetched, exiting")
                sys.exit(1)

            logger.info("Fetching bitbake from remote repository %s" % settings.BITBAKE_REPO_URL)
            if not os.path.exists(bitbakepath):
                out = utils.runcmd("git clone %s %s" % (settings.BITBAKE_REPO_URL, 'bitbake'), fetchdir, logger=logger)
            else:
                out = utils.runcmd("git fetch", bitbakepath, logger=logger)

        # Process and extract data from each layer
        # We now do this by calling out to a separate script; doing otherwise turned out to be
        # unreliable due to leaking memory (we're using bitbake internals in a manner in which
        # they never get used during normal operation).
        for branch in branches:
            for layer in layerquery:
                if layer.vcs_url in failedrepos:
                    logger.info("Skipping update of layer %s as fetch of repository %s failed" % (layer.name, layer.vcs_url))

                urldir = layer.get_fetch_dir()
                repodir = os.path.join(fetchdir, urldir)

                branchobj = utils.get_branch(branch)
                if branchobj.update_environment:
                    cmdprefix = branchobj.update_environment.get_command()
                else:
                    cmdprefix = 'python'
                cmd = '%s update_layer.py -l %s -b %s' % (cmdprefix, layer.name, branch)
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
                logger.debug('Running layer update command: %s' % cmd)
                ret = run_command_interruptible(cmd)
                if ret == 254:
                    # Interrupted by user, break out of loop
                    break

    finally:
        utils.unlock_file(lockfile)

    sys.exit(0)


if __name__ == "__main__":
    main()
