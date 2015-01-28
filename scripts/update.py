#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Fetch layer repositories and update layer index database
#
# Copyright (C) 2013 - 2015 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
# Contributor: Aníbal Limón <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import shutil

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../lib')))

import optparse
import logging
import utils

utils.setup_django()
import settings

import warnings
warnings.filterwarnings("ignore", category = DeprecationWarning)

logger = utils.logger_create('LayerindexUpdate')

from layerindex_update import LayerindexUpdater

def main():
    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-b", "--branch",
            help = "Specify branch to update",
            action="store", dest="branch", default='master')
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
    if settings.APPLICATION == 'rrs':
        parser.add_option("", "--only-layerindex",
                help = "Only run layerindex update",
                action="store_true", dest="only_layerindex")
        parser.add_option("", "--recipe",
                help = "Specify recipe to update",
                action="store", dest="recipe")
        parser.add_option("", "--recipe-distros",
                help = "Only update recipe distros",
                action="store_true", dest="recipe_distros")
        parser.add_option("", "--recipe-upgrades",
                help = "Only update recipe upgrades",
                action="store_true", dest="recipe_upgrades")
        parser.add_option("", "--recipe-upstream",
                help = "Only update recipe upstream",
                action="store_true", dest="recipe_upstream")

    options, args = parser.parse_args(sys.argv)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)

    if options.fullreload:
        options.reload = True

    logger.setLevel(options.loglevel)

    branch = utils.get_branch(options.branch)
    if not branch:
        logger.error("Specified branch %s is not valid" % options.branch)
        sys.exit(1)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)
    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)

    lockfn = os.path.join(fetchdir, "layerindex.lock")
    lockfile = utils.lock_file(lockfn)
    if not lockfile:
        logger.error("Layer index lock timeout expired")
        sys.exit(1)

    bitbakepath = update_repo(fetchdir, 'bitbake', settings.BITBAKE_REPO_URL,
            False, logger)
    if settings.APPLICATION == 'rrs':
       pokypath = update_repo(fetchdir, 'poky', settings.POKY_REPO_URL,
               True, logger)
       # add path for use oe-core libraries
       sys.path.insert(0, os.path.realpath(os.path.join(pokypath, 'meta', 'lib')))
       # add support for load distro include files
       os.environ['BBPATH'] = os.path.join(pokypath, 'meta-yocto')

    (layerquery, fetchedrepos, failedrepos) = update_layers(options, fetchdir, logger)
    (tinfoil, tempdir) = get_tinfoil(branch, bitbakepath, options, logger)

    layerindex_updater = LayerindexUpdater(options, fetchdir, layerquery, fetchedrepos,
            failedrepos, logger)
    layerindex_updater.run(tinfoil)

    if settings.APPLICATION == 'rrs':
        from rrs_update import RrsUpdater
        rrs_updater = RrsUpdater(fetchdir, options, layerquery,
                                    fetchedrepos, failedrepos,
                                    pokypath, logger)
        if not options.only_layerindex:
            rrs_updater.run(tinfoil)

    shutil.rmtree(tempdir)
    utils.unlock_file(lockfile)

def update_repo(fetchdir, repo_name, repo_url, pull, logger):
    path = os.path.join(fetchdir, repo_name)

    logger.info("Fetching %s from remote repository %s"
                    % (repo_name, repo_url))
    if not os.path.exists(path):
        out = utils.runcmd("git clone %s %s" %
                (repo_url, repo_name), fetchdir,
                logger = logger)
    else:
        if pull == True:
            out = utils.runcmd("git pull", path, logger = logger)
        else:
            out = utils.runcmd("git fetch", path, logger = logger)

    return path

def update_layers(options, fetchdir, logger):
    from layerindex.models import LayerItem

    fetchedrepos = []
    failedrepos = []

    if options.layers:
        layerquery = LayerItem.objects.filter(classic =
                False).filter(name__in = options.layers.split(','))
    else:
        layerquery = LayerItem.objects.filter(classic =
                False).filter(status = 'P') # All published layers

    if layerquery.count() == 0:
        logger.info("No published layers to update")
        sys.exit(1)

    # Fetch latest metadata from repositories
    # Handle multiple layers in a single repo
    for layer in layerquery:
        urldir = layer.get_fetch_dir()
        repodir = os.path.join(fetchdir, urldir)

        if not (layer.vcs_url in fetchedrepos or layer.vcs_url in
                failedrepos):
            logger.info("Fetching remote repository %s" %
                    layer.vcs_url)

            out = None
            try:
                if not os.path.exists(repodir):
                    out = utils.runcmd("git clone %s %s" %
                            (layer.vcs_url, urldir), fetchdir,
                            logger = logger)
                else:
                    out = utils.runcmd("git fetch", repodir, logger =
                            logger)
            except Exception as e:
                logger.error("Fetch of layer %s failed: %s" %
                        (layer.name, str(e)))
                failedrepos.append(layer.vcs_url)
                continue

            fetchedrepos.append(layer.vcs_url)

    if not fetchedrepos:
        logger.error("No repositories could be fetched, exiting")
        sys.exit(1)

    return (layerquery, fetchedrepos, failedrepos)

def get_tinfoil(branch, bitbakepath, options, logger):
    import recipeparse
    try:
        (tinfoil, tempdir) = recipeparse.init_parser(settings, branch, bitbakepath,
                                nocheckout = options.nocheckout, logger = logger)
    except recipeparse.RecipeParseError as e:
        logger.error(str(e))
        sys.exit(1)

    # Clear the default value of SUMMARY so that we can use DESCRIPTION instead
    # if it hasn't been set
    tinfoil.config_data.setVar('SUMMARY', '')
    # Clear the default value of DESCRIPTION so that we can see where it's not set
    tinfoil.config_data.setVar('DESCRIPTION', '')
    # Clear the default value of HOMEPAGE ('unknown')
    tinfoil.config_data.setVar('HOMEPAGE', '')
    # Set a blank value for LICENSE so that it doesn't cause the parser to die
    # (e.g. with meta-ti -, why won't they just fix that?!)
    tinfoil.config_data.setVar('LICENSE', '')

    return (tinfoil, tempdir)

if __name__ == "__main__":
    main()
