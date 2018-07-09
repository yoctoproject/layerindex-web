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
from datetime import datetime, timedelta
from distutils.version import LooseVersion
import utils
import operator
import re
import multiprocessing

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = utils.logger_create('LayerIndexUpdate')

# Ensure PythonGit is installed (buildhistory_analysis needs it)
try:
    import git
except ImportError:
    logger.error("Please install PythonGit 0.3.1 or later in order to use this script")
    sys.exit(1)


def prepare_update_layer_command(options, branch, layer, initial=False):
    """Prepare the update_layer.py command line"""
    if branch.update_environment:
        cmdprefix = branch.update_environment.get_command()
    else:
        cmdprefix = 'python3'
    cmd = '%s update_layer.py -l %s -b %s' % (cmdprefix, layer.name, branch.name)
    if options.reload:
        cmd += ' --reload'
    if options.fullreload:
        cmd += ' --fullreload'
    if options.nocheckout:
        cmd += ' --nocheckout'
    if options.dryrun:
        cmd += ' -n'
    if initial:
        cmd += ' -i'
    if options.loglevel == logging.DEBUG:
        cmd += ' -d'
    elif options.loglevel == logging.ERROR:
        cmd += ' -q'
    if options.keep_temp:
        cmd += ' --keep-temp'
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

def fetch_repo(vcs_url, repodir, urldir, fetchdir, layer_name):
    logger.info("Fetching remote repository %s" % vcs_url)
    try:
        if not os.path.exists(repodir):
            utils.runcmd("git clone %s %s" % (vcs_url, urldir), fetchdir, logger=logger, printerr=False)
        else:
            utils.runcmd("git fetch -p", repodir, logger=logger, printerr=False)
        return (vcs_url, None)
    except subprocess.CalledProcessError as e:
        logger.error("Fetch of layer %s failed: %s" % (layer_name, e.output))
        return (vcs_url, e.output)

def print_subdir_error(newbranch, layername, vcs_subdir, branchdesc):
    # This will error out if the directory is completely invalid or had never existed at this point
    # If it previously existed but has since been deleted, you will get the revision where it was
    # deleted - so we need to handle that case separately later
    if newbranch:
        logger.info("Skipping update of layer %s for branch %s - subdirectory %s does not exist on this branch" % (layername, branchdesc, vcs_subdir))
    elif vcs_subdir:
        logger.error("Subdirectory for layer %s does not exist on branch %s - if this is legitimate, the layer branch record should be deleted" % (layername, branchdesc))

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
    parser.add_option("-t", "--timeout",
            help = "Specify timeout in seconds to get layerindex.lock. Default is 30 seconds.",
            type="int", action="store", dest="timeout", default=30)
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
    parser.add_option("", "--keep-temp",
            help = "Preserve temporary directory at the end instead of deleting it",
            action="store_true")

    options, args = parser.parse_args(sys.argv)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)

    utils.setup_django()
    import settings
    from layerindex.models import Branch, LayerItem, Update, LayerUpdate, LayerBranch

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


    # We deliberately exclude status == 'X' ("no update") here
    layerquery_all = LayerItem.objects.filter(classic=False).filter(status='P')
    if layerquery_all.count() == 0:
        logger.info("No published layers to update")
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
        layerquery = layerquery_all
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

    allrepos = {}
    fetchedresult = []
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
        lockfile = utils.lock_file(lockfn, options.timeout, logger)
        if not lockfile:
            logger.error("Layer index lock timeout expired")
            sys.exit(1)
        try:
            bitbakepath = os.path.join(fetchdir, 'bitbake')

            if not options.nofetch:
                # Make sure oe-core is fetched since recipe parsing requires it
                layerquery_core = LayerItem.objects.filter(classic=False).filter(name=settings.CORE_LAYER_NAME)
                if layerquery_core in layerquery:
                    layerquery_fetch = list(layerquery)
                else:
                    layerquery_fetch = list(layerquery) + list(layerquery_core)
                # Fetch latest metadata from repositories
                for layer in layerquery_fetch:
                    # Handle multiple layers in a single repo
                    urldir = layer.get_fetch_dir()
                    repodir = os.path.join(fetchdir, urldir)
                    if layer.vcs_url not in allrepos:
                        allrepos[layer.vcs_url] = (repodir, urldir, fetchdir, layer.name)
                # Add bitbake
                allrepos[settings.BITBAKE_REPO_URL] = (bitbakepath, "bitbake", fetchdir, "bitbake")
                # Parallel fetching
                pool = multiprocessing.Pool(int(settings.PARALLEL_JOBS))
                for url in allrepos:
                    fetchedresult.append(pool.apply_async(fetch_repo, \
                        (url, allrepos[url][0], allrepos[url][1], allrepos[url][2], allrepos[url][3],)))
                pool.close()
                pool.join()

                for url in fetchedresult[:]:
                    # The format is (url, error), the error is None when succeed.
                    if url.get()[1]:
                        failedrepos[url.get()[0]] = url.get()[1]
                    else:
                        fetchedrepos.append(url.get()[0])

                if not (fetchedrepos or update_bitbake):
                    logger.error("No repositories could be fetched, exiting")
                    sys.exit(1)

            if options.actual_branch:
                update_actual_branch(layerquery, fetchdir, branches[0], options, update_bitbake, bitbakepath)
                return

            # Process and extract data from each layer
            # We now do this by calling out to a separate script; doing otherwise turned out to be
            # unreliable due to leaking memory (we're using bitbake internals in a manner in which
            # they never get used during normal operation).
            last_rev = {}
            failed_layers = {}
            for branch in branches:
                failed_layers[branch] = []
                # If layer_A depends(or recommends) on layer_B, add layer_B before layer_A
                deps_dict_all = {}
                layerquery_sorted = []
                collections = set()
                branchobj = utils.get_branch(branch)
                for layer in layerquery_all:
                    # Get all collections from database, but we can't trust the
                    # one which will be updated since its collections maybe
                    # changed (different from database).
                    if layer in layerquery:
                        continue
                    layerbranch = layer.get_layerbranch(branch)
                    if layerbranch:
                        collections.add((layerbranch.collection, layerbranch.version))

                for layer in layerquery:
                    layerbranch = layer.get_layerbranch(branch)
                    branchname = branch
                    branchdesc = branch
                    newbranch = False
                    branchobj = utils.get_branch(branch)
                    if layerbranch:
                        if layerbranch.actual_branch:
                            branchname = layerbranch.actual_branch
                            branchdesc = "%s (%s)" % (branch, branchname)
                    else:
                        # LayerBranch doesn't exist for this branch, create it temporarily
                        # (we won't save this - update_layer.py will do the actual creation
                        # if it gets called).
                        newbranch = True
                        layerbranch = LayerBranch()
                        layerbranch.layer = layer
                        layerbranch.branch = branchobj
                        layerbranch_source = layer.get_layerbranch(branchobj)
                        if not layerbranch_source:
                            layerbranch_source = layer.get_layerbranch(None)
                        if layerbranch_source:
                            layerbranch.vcs_subdir = layerbranch_source.vcs_subdir

                    # Collect repo info
                    urldir = layer.get_fetch_dir()
                    repodir = os.path.join(fetchdir, urldir)
                    repo = git.Repo(repodir)
                    assert repo.bare == False
                    try:
                        # Always get origin/branchname, so it raises error when branch doesn't exist when nocheckout
                        topcommit = repo.commit('origin/%s' % branchname)
                        if options.nocheckout:
                            topcommit = repo.commit('HEAD')
                    except:
                        if newbranch:
                            logger.info("Skipping update of layer %s - branch %s doesn't exist" % (layer.name, branchdesc))
                        else:
                            logger.info("layer %s - branch %s no longer exists, removing it from database" % (layer.name, branchdesc))
                            if not options.dryrun:
                                layerbranch.delete()
                        continue

                    if layerbranch.vcs_subdir and not options.nocheckout:
                        # Find latest commit in subdirectory
                        # A bit odd to do it this way but apparently there's no other way in the GitPython API
                        topcommit = next(repo.iter_commits('origin/%s' % branchname, paths=layerbranch.vcs_subdir), None)
                        if not topcommit:
                            print_subdir_error(newbranch, layer.name, layerbranch.vcs_subdir, branchdesc)
                            if not (newbranch and layerbranch.vcs_subdir):
                                logger.error("Failed to get last revision for layer %s on branch %s" % (layer.name, branchdesc))
                            continue

                    if layerbranch.vcs_last_rev == topcommit.hexsha and not update.reload:
                        logger.info("Layer %s is already up-to-date for branch %s" % (layer.name, branchdesc))
                        collections.add((layerbranch.collection, layerbranch.version))
                        continue
                    else:
                        # Check out appropriate branch
                        if not options.nocheckout:
                            utils.checkout_layer_branch(layerbranch, repodir, logger=logger)
                        layerdir = os.path.join(repodir, layerbranch.vcs_subdir)
                        if layerbranch.vcs_subdir and not os.path.exists(layerdir):
                            print_subdir_error(newbranch, layer.name, layerbranch.vcs_subdir, branchdesc)
                            continue

                        if not os.path.exists(os.path.join(layerdir, 'conf/layer.conf')):
                            logger.error("conf/layer.conf not found for layer %s - is subdirectory set correctly?" % layer.name)
                            continue

                    cmd = prepare_update_layer_command(options, branchobj, layer, initial=True)
                    logger.debug('Running layer update command: %s' % cmd)
                    ret, output = utils.run_command_interruptible(cmd)
                    logger.debug('output: %s' % output)
                    if ret == 254:
                        # Interrupted by user, break out of loop
                        logger.info('Update interrupted, exiting')
                        sys.exit(254)
                    elif ret != 0:
                        continue
                    col = re.search("^BBFILE_COLLECTIONS = \"(.*)\"", output, re.M).group(1) or ''
                    ver = re.search("^LAYERVERSION = \"(.*)\"", output, re.M).group(1) or ''
                    deps = re.search("^LAYERDEPENDS = \"(.*)\"", output, re.M).group(1) or ''
                    recs = re.search("^LAYERRECOMMENDS = \"(.*)\"", output, re.M).group(1) or ''

                    deps_dict = utils.explode_dep_versions2(bitbakepath, deps)
                    recs_dict = utils.explode_dep_versions2(bitbakepath, recs)
                    if not (deps_dict or recs_dict):
                        # No depends, add it firstly
                        layerquery_sorted.append(layer)
                        collections.add((col, ver))
                        continue
                    deps_dict_all[layer] = {'deps': deps_dict, \
                                            'recs': recs_dict, \
                                            'collection': col, \
                                            'version': ver}

                # Move deps_dict_all to layerquery_sorted orderly
                if deps_dict_all:
                    logger.info("Sorting layers for branch %s" % branch)
                while True:
                    deps_dict_all_copy = deps_dict_all.copy()
                    for layer, value in deps_dict_all_copy.items():
                        for deps_recs in ('deps', 'recs'):
                            for req_col, req_ver_list in value[deps_recs].copy().items():
                                matched = False
                                if req_ver_list:
                                    req_ver = req_ver_list[0]
                                else:
                                    req_ver = None
                                if utils.is_deps_satisfied(req_col, req_ver, collections):
                                    del(value[deps_recs][req_col])
                        if not (value['deps'] or value['recs']):
                            # All the depends are in collections:
                            del(deps_dict_all[layer])
                            layerquery_sorted.append(layer)
                            collections.add((value['collection'], value['version']))

                    if not len(deps_dict_all):
                        break

                    finished = True
                    # If nothing changed after a run, drop recs and try again
                    if operator.eq(deps_dict_all_copy, deps_dict_all):
                        for layer, value in deps_dict_all.items():
                            if value['recs'] and not value['deps']:
                                # Add it if recs isn't satisfied only.
                                logger.warn('Adding %s without LAYERRECOMMENDS...' % layer.name)
                                del(deps_dict_all[layer])
                                layerquery_sorted.append(layer)
                                collections.add((value['collection'], value['version']))
                                failed_msg = '%s: Added without LAYERRECOMMENDS' % layer.name
                                failed_layers[branch].append(failed_msg)
                                finished = False
                                break
                        if not finished:
                            continue
                        logger.warning("Cannot find required collections on branch %s:" % branch)
                        for layer, value in deps_dict_all.items():
                            logger.warn('%s: LAYERDEPENDS: %s LAYERRECOMMENDS: %s' % (layer.name, value['deps'], value['recs']))
                            if value['deps']:
                                failed_layers[branch].append('%s: Failed to add since LAYERDEPENDS is not satisfied' % layer.name)
                            else:
                                # Should never come here
                                logger.error("Unexpected errors when sorting layers")
                                sys.exit(1)
                        logger.warning("Known collections on branch %s: %s" % (branch, collections))
                        break

                for layer in layerquery_sorted:
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

                    cmd = prepare_update_layer_command(options, branchobj, layer)
                    logger.debug('Running layer update command: %s' % cmd)
                    layerupdate.started = datetime.now()
                    ret, output = utils.run_command_interruptible(cmd)
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
                        logger.info('Update interrupted, exiting')
                        sys.exit(254)
            if failed_layers:
                for branch, err_msg_list in failed_layers.items():
                    if err_msg_list:
                        print()
                        logger.error("Issues found on branch %s:\n    %s" % (branch, "\n    ".join(err_msg_list)))
                        print()
        finally:
            utils.unlock_file(lockfile)

    except KeyboardInterrupt:
        logger.info('Update interrupted, exiting')
        sys.exit(254)
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
