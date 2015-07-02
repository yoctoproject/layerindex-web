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

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, update_repo, get_pv_type
common_setup()
from layerindex import utils, recipeparse
from layerindex.update import split_recipe_fn

utils.setup_django()
from django.db import transaction
import settings
import optparse
import logging

from layerindex.models import Recipe, LayerItem, LayerBranch
from rrs.models import Maintainer, RecipeUpgrade

"""
    Store upgrade into RecipeUpgrade model.
"""
def _create_upgrade(recipe, pv, commit, title, info, logger):
    from email.utils import parsedate_tz, mktime_tz

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
    Returns recipe name and version by recipe filename.
"""
def _get_recipe_name_and_version(fullpath):
    import re

    (pn, pv) = split_recipe_fn(fullpath)

    with open(fullpath, 'rb') as f:
        for line in f.read().split('\n'):
            m = re.match("PV = \"(.*)\"", line)
            if m:
                pv = m.group(1)

                # remove ${SRCREV}, ${SRC...}
                m = re.match(".*(\$\{.*\})", pv)
                if m:
                    pv = pv.replace(m.group(1), '')

    return (pn, pv)

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

"""
    Upgrade history handler.
"""
def upgrade_history(options, logger):
    pokypath = update_repo(settings.LAYER_FETCH_DIR, 'poky', settings.POKY_REPO_URL,
        True, logger)
    sys.path.insert(0, os.path.join(pokypath, 'bitbake', 'lib'))
    sys.path.insert(0, os.path.join(pokypath, 'meta', 'lib'))
    from bb.utils import vercmp_string
    from oe.recipeutils import get_recipe_pv_without_srcpv

    layername = settings.CORE_LAYER_NAME
    branchname = "master"
    layer = LayerItem.objects.filter(name__iexact = layername)[0]
    if not layer:
        logger.error("Core layer does not exist, please set into settings.")
        sys.exit(1)
    urldir = layer.get_fetch_dir()
    layerbranch = LayerBranch.objects.filter(layer__name__iexact =
                        layername).filter(branch__name__iexact =
                        branchname)[0]
    repodir = os.path.join(settings.LAYER_FETCH_DIR, urldir)
    layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

    now = datetime.today()
    today = now.strftime("%Y-%m-%d")
    if options.initial:
        # starting date of the yocto project
        since = "2010-06-11"
        #RecipeUpgrade.objects.all().delete()
    else:
        since = (now - timedelta(days=8)).strftime("%Y-%m-%d")

    branch_name_tmp = "recipe_upgrades"
    utils.runcmd("git checkout origin/master -f", repodir)
    # try to delete temp_branch if exists
    try:
        utils.runcmd("git branch -D %s" % (branch_name_tmp), repodir,
                logger=logger)
    except:
        pass

    commits = utils.runcmd("git log --since='" + since + "' --until='" +
                            today + "' --format='%H' --reverse", repodir,
                            logger=logger)

    transaction.enter_transaction_management()
    transaction.managed(True)
    if options.initial:
        logger.debug("Adding initial upgrade history ....")

        title = "Initial import."
        info = "No maintainer;;Fri, 11 Jun 2010 00:00:00 +0000;Fri, 11 Jun 2010 00:00:00 +0000"

        ct = commits.split('\n')[0]
        utils.runcmd("git checkout %s -b %s -f" % (ct, branch_name_tmp),
                        repodir, logger=logger)

        for recipe in Recipe.objects.filter(layerbranch=layerbranch):
            fns = utils.runcmd("find . -name \"%s*.bb\" -type f" % recipe.bpn,
                    repodir, logger=logger)

            pn = ''
            pv = ''
            for fn in fns.split('\n'):
                if not fn:
                    continue

                # validate if is the same recipe
                if recipe.pn != split_recipe_fn(fn)[0]:
                    continue

                (npn, npv) = _get_recipe_name_and_version(os.path.join(repodir, fn))

                if not pv:
                    pn = npn
                    pv = npv
                else:
                    (pv_tmp, _, _) = get_recipe_pv_without_srcpv(pv, get_pv_type(pv))
                    (npv_tmp, _, _) = get_recipe_pv_without_srcpv(npv, get_pv_type(npv))

                    if npv == 'git':
                        continue
                    elif pv_tmp == 'git' or vercmp_string(pv_tmp, npv_tmp) == -1:
                        pn = npn
                        pv = npv

            if not pv:
                logger.debug("%s: Don't exist at initial." % (recipe.pn))
                continue

            logger.debug("%s: Initial upgrade ( -> %s)." % (recipe.pn, pv))
            _create_upgrade(recipe, pv, '', title, info, logger)

        utils.runcmd("git checkout master -f", repodir, logger=logger)
        utils.runcmd("git branch -D %s" % (branch_name_tmp), repodir, logger=logger)
    transaction.commit()
    transaction.leave_transaction_management()

    transaction.enter_transaction_management()
    transaction.managed(True)
    logger.debug("Adding upgrade history from %s to %s ..." % (since, today))
    for ct in commits.split("\n"):
        if ct != "":
            logger.debug("Analysing commit %s ..." % ct)

            utils.runcmd("git checkout %s -b %s -f" % (ct, branch_name_tmp),
                    repodir, logger=logger)

            fns = _get_recipes_filenames(ct, repodir, layerdir, logger)
            for fn in fns:
                (pn, pv) = _get_recipe_name_and_version(fn)

                try:
                    recipe = Recipe.objects.get(layerbranch = layerbranch,
                            pn__exact = pn)
                except Exception as e:
                    # Most probably a native found
                    logger.warn("%s: Not found in database, %s." %
                                (pn, str(e)))
                    continue

                try:
                    latest_upgrade = RecipeUpgrade.objects.filter(
                            recipe = recipe).order_by('-commit_date')[0]
                    prev_pv = latest_upgrade.version
                except Exception as e:
                    logger.debug("%s: No previous version found." % (pn))
                    prev_pv = None

                try:
                    title = utils.runcmd("git log --format='%s' -n 1 " + ct,
                                            repodir, logger=logger)
                    info = utils.runcmd("git log  --format='%an;%ae;%ad;%cd' --date=rfc -n 1 " \
                            + ct, destdir=repodir, logger=logger)

                    if not prev_pv:
                        logger.debug("%s: Initial upgrade ( -> %s)." % (recipe.pn, pv))
                        _create_upgrade(recipe, pv, ct, title, info, logger)
                    else:
                        (ppv, _, _) = get_recipe_pv_without_srcpv(prev_pv,
                                get_pv_type(prev_pv))
                        (npv, _, _) = get_recipe_pv_without_srcpv(pv,
                                get_pv_type(pv))

                        if npv == 'git':
                            continue
                        elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                            logger.debug("%s: Detected upgrade (%s -> %s)" \
                                    " in ct %s." % (pn, prev_pv, pv, ct))
                            _create_upgrade(recipe, pv, ct, title, info, logger)
                except:
                    logger.error("%s: vercmp_string, %s - %s" % (recipe.pn,
                        prev_pv, pv))

            utils.runcmd("git checkout master -f", repodir, logger=logger)
            utils.runcmd("git branch -D %s" % (branch_name_tmp), repodir, logger=logger)

    transaction.commit()
    transaction.leave_transaction_management()


if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-i", "--initial",
            help = "Do initial population of upgrade histories",
            action="store_true", dest="initial", default=False)

    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    
    logger = utils.logger_create("HistoryUpgrade")
    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    upgrade_history(options, logger)
