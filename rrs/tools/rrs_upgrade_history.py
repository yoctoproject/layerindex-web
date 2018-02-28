#!/usr/bin/env python

# Standalone script which rebuilds the history of all the upgrades.
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from datetime import datetime
from datetime import timedelta

import sys
import os.path
import optparse
import logging

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_pv_type, load_recipes, \
        get_logger, DryRunRollbackException

common_setup()
from layerindex import utils, recipeparse
from layerindex.update_layer import split_recipe_fn

utils.setup_django()
from django.db import transaction
import settings

logger = get_logger("HistoryUpgrade", settings)
fetchdir = settings.LAYER_FETCH_DIR
if not fetchdir:
    logger.error("Please set LAYER_FETCH_DIR in settings.py")
    sys.exit(1)

# setup bitbake
bitbakepath = os.path.join(fetchdir, 'bitbake')
sys.path.insert(0, os.path.join(bitbakepath, 'lib'))
from bb.utils import vercmp_string

"""
    Store upgrade into RecipeUpgrade model.
"""
def _save_upgrade(recipe, pv, commit, title, info, logger):
    from email.utils import parsedate_tz, mktime_tz
    from rrs.models import Maintainer, RecipeUpgrade

    maintainer_name = info.split(';')[0]
    maintainer_email = info.split(';')[1]
    author_date = info.split(';')[2]
    commit_date = info.split(';')[3]

    maintainer = Maintainer.create_or_update(maintainer_name, maintainer_email)

    upgrade = RecipeUpgrade()
    upgrade.recipe = recipe
    upgrade.maintainer = maintainer
    upgrade.author_date = datetime.utcfromtimestamp(mktime_tz(
                                    parsedate_tz(author_date)))
    upgrade.commit_date = datetime.utcfromtimestamp(mktime_tz(
                                    parsedate_tz(commit_date)))
    upgrade.version = pv
    upgrade.sha1 = commit
    upgrade.title = title.strip()
    upgrade.save()

"""
    Create upgrade receives new recipe_data and cmp versions.
"""
def _create_upgrade(recipe_data, layerbranch, ct, title, info, logger, initial=False):
    from layerindex.models import Recipe
    from rrs.models import RecipeUpgrade

    pn = recipe_data.getVar('PN', True)
    pv = recipe_data.getVar('PV', True)

    try:
        recipe = Recipe.objects.get(pn=pn, layerbranch=layerbranch)
    except Exception as e:
        logger.warn("%s: Not found in Layer branch %s." %
                    (pn, str(layerbranch)))
        return

    try:
        latest_upgrade = RecipeUpgrade.objects.filter(
                recipe = recipe).order_by('-commit_date')[0]
        prev_pv = latest_upgrade.version
    except:
        prev_pv = None

    if prev_pv is None:
        logger.debug("%s: Initial upgrade ( -> %s)." % (recipe.pn, pv))
        _save_upgrade(recipe, pv, ct, title, info, logger)
    else:
        from common import get_recipe_pv_without_srcpv

        (ppv, _, _) = get_recipe_pv_without_srcpv(prev_pv,
                get_pv_type(prev_pv))
        (npv, _, _) = get_recipe_pv_without_srcpv(pv,
                get_pv_type(pv))

        try:
            if npv == 'git':
                logger.debug("%s: Avoiding upgrade to unversioned git." % \
                        (recipe.pn)) 
            elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                if initial is True:
                    logger.debug("%s: Update initial upgrade ( -> %s)." % \
                            (recipe.pn, pv)) 
                    latest_upgrade.version = pv
                    latest_upgrade.save()
                else:
                    logger.debug("%s: detected upgrade (%s -> %s)" \
                            " in ct %s." % (pn, prev_pv, pv, ct))
                    _save_upgrade(recipe, pv, ct, title, info, logger)
        except:
            logger.error("%s: fail to detect upgrade (%s -> %s)" \
                            " in ct %s." % (pn, prev_pv, pv, ct))


"""
    Returns a list containing the fullpaths to the recipes from a commit.
"""
def _get_recipes_filenames(ct, repodir, layerdir, logger):
    ct_files = []
    layerdir_start = os.path.normpath(layerdir) + os.sep

    files = utils.runcmd("git log --name-only --format='%n' -n 1 " + ct,
                            repodir, logger=logger)

    for f in files.split("\n"):
        if f != "":
            fullpath = os.path.join(repodir, f)
            # Skip deleted files in commit
            if not os.path.exists(fullpath):
                continue
            (typename, _, filename) = recipeparse.detect_file_type(fullpath,
                                        layerdir_start)
            if typename == 'recipe':
                ct_files.append(fullpath)

    return ct_files

def do_initial(layerbranch, ct, logger, dry_run):
    layer = layerbranch.layer
    urldir = str(layer.get_fetch_dir())
    repodir = os.path.join(fetchdir, urldir)
    layerdir = os.path.join(repodir, str(layerbranch.vcs_subdir))

    utils.runcmd("git checkout %s" % ct,
                    repodir, logger=logger)
    utils.runcmd("git clean -dfx", repodir, logger=logger)

    title = "Initial import at 1.6 release start."
    info = "No maintainer;;Mon, 11 Nov 2013 00:00:00 +0000;Mon, 11 Nov 2013 00:00:00 +0000"

    (tinfoil, d, recipes) = load_recipes(layerbranch, bitbakepath,
                            fetchdir, settings, logger, nocheckout=True)

    try:
        with transaction.atomic():
            for recipe_data in recipes:
                _create_upgrade(recipe_data, layerbranch, '', title,
                        info, logger, initial=True)
            if dry_run:
                raise DryRunRollbackException
    except DryRunRollbackException:
        pass

    tinfoil.shutdown()

def do_loop(layerbranch, ct, logger, dry_run):
    layer = layerbranch.layer
    urldir = str(layer.get_fetch_dir())
    repodir = os.path.join(fetchdir, urldir)
    layerdir = os.path.join(repodir, str(layerbranch.vcs_subdir))

    utils.runcmd("git checkout %s" % ct,
            repodir, logger=logger)
    utils.runcmd("git clean -dfx", repodir, logger=logger)

    fns = _get_recipes_filenames(ct, repodir, layerdir, logger)
    if not fns:
        return

    (tinfoil, d, recipes) = load_recipes(layerbranch, bitbakepath,
                        fetchdir, settings, logger, recipe_files=fns,
                        nocheckout=True)

    title = utils.runcmd("git log --format='%s' -n 1 " + ct,
                                    repodir, logger=logger)
    info = utils.runcmd("git log  --format='%an;%ae;%ad;%cd' --date=rfc -n 1 " \
                    + ct, destdir=repodir, logger=logger)
    try:
        with transaction.atomic():
            for recipe_data in recipes:
                _create_upgrade(recipe_data, layerbranch, ct, title,
                                    info, logger)
            if dry_run:
                raise DryRunRollbackException
    except DryRunRollbackException:
        pass

    tinfoil.shutdown()


"""
    Upgrade history handler.
"""
def upgrade_history(options, logger):
    from layerindex.models import LayerBranch
    from rrs.models import MaintenancePlan

    # start date
    now = datetime.today()
    today = now.strftime("%Y-%m-%d")
    if options.initial:
        # starting date of the yocto project 1.6 release
        since = "2013-11-11"
        #RecipeUpgrade.objects.all().delete()
    else:
        since = (now - timedelta(days=8)).strftime("%Y-%m-%d")

    maintplans = MaintenancePlan.objects.filter(updates_enabled=True)
    if not maintplans.exists():
        logger.error('No enabled maintenance plans found')
        sys.exit(1)
    for maintplan in maintplans:
        for maintplanbranch in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = maintplanbranch.layerbranch
            layer = layerbranch.layer
            urldir = layer.get_fetch_dir()
            repodir = os.path.join(fetchdir, urldir)
            layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

            commits = utils.runcmd("git log --since='" + since +
                                    "' --format='%H' --reverse", repodir,
                                    logger=logger)
            commit_list = commits.split('\n')

            if options.initial:
                logger.debug("Adding initial upgrade history ....")

                ct = commit_list.pop(0)
                do_initial(layerbranch, ct, logger, options.dry_run)

            logger.debug("Adding upgrade history from %s to %s ..." % (since, today))
            for ct in commit_list:
                if ct:
                    logger.debug("Analysing commit %s ..." % ct)
                    do_loop(layerbranch, ct, logger, options.dry_run)

            if commit_list:
                utils.runcmd("git clean -dfx", repodir, logger=logger)

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-i", "--initial",
            help = "Do initial population of upgrade histories",
            action="store_true", dest="initial", default=False)

    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)

    parser.add_option("--dry-run",
            help = "Do not write any data back to the database",
            action="store_true", dest="dry_run", default=False)

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    upgrade_history(options, logger)
