#!/usr/bin/env python

# Standalone script which rebuilds the history of all the upgrades.
#
# To detect package versions of the recipes the script uses the name of the recipe.
# This doesn't work for some git and svn recipes, but is good enough for historical data.
#
# Copyright (C) 2014 - 2015 Intel Corporation
# Author: Marius Avram <marius.avram@intel.com>
# Contributor: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from datetime import datetime
from datetime import timedelta

import sys
import os.path

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../lib')))
import utils
import recipeparse

utils.setup_django()
import settings
import optparse
import logging

from layerindex.models import Recipe, LayerItem, LayerBranch
from rrs.models import Maintainer, RecipeUpgrade

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../rrs_update')))
from recipe_upgrade import create_upgrade

"""
    Gets Recipe that match pn
"""
def get_recipe(pn):
    recipe = None
    try:
        recipe = Recipe.objects.get(pn = pn)
    except Recipe.DoesNotExist:
        # If exact recipe name does not exits find a matching pattern
        try:
            recipe = Recipe.objects.filter(pn__regex=r'.*%s.*' % pn)[0]
        except:
            pass
    return recipe

""" 
    Detects if the version given as a parameter is newver than the version
    of the latest upgrade.
"""
def is_newer_version(pn, pv):
    recipe = get_recipe(pn)

    if not recipe:
        return False

    try:
        latest_upgrade = RecipeUpgrade.objects.filter(
                            recipe = recipe).filter(version = pv)[0]
    except:
        return True

    return False

"""
    Insert dummy upgrades for the first day of the yocto project.
    Needed becase a version reference is needed.
"""
def initial_recipes(layerdir, date, logger):
    recipes = {}

    logger.debug("Adding initial versions:")

    # Collect unique info about the existing recipes 
    layerdir_start = os.path.normpath(layerdir) + os.sep
    for root, dirs, files in os.walk(layerdir):
        if '.git' in dirs:
            dirs.remove('.git')
        for f in files:
            fullpath = os.path.join(root, f)
            (typename, _, filename) = recipeparse.detect_file_type(
                                        fullpath, layerdir_start)
            if typename == 'recipe':
                (pn, pv) = recipeparse.split_recipe_fn(fullpath)
                logger.debug("pn %s; pv %s" % (pn, pv))
                insert_clean_pn(recipes, pn, pv)

    logger.debug("Inserting into database...") 

    # Insert initial version of every recipe in the database.
    # Leave the maintainer field blank to know this are not actually upgrades.
    maintainer = Maintainer.objects.get(id = 0) # No maintainer
    for pn, pv in recipes.iteritems():
        try:
            recipe = Recipe.objects.get(pn=pn)
        except Recipe.DoesNotExist:
            continue
        upgrade = RecipeUpgrade()
        upgrade.recipe = recipe
        upgrade.maintainer = maintainer
        upgrade.author_date = date
        upgrade.commit_date = date
        upgrade.version = pv
        upgrade.save()

    return recipes

"""
    Insert new recipes in the recipes dictionary.
"""
def insert_clean_pn(recipes, pn, pv):
    # Do not insert natives if original in dictionary
    if (pn.replace("-native", "").replace("nativesdk-", "") in recipes):
        return

    # Remove natives when original found
    if "nativesdk-" + pn in recipes:
        del recipes["nativesdk-" + pn]
    if pn + "-native" in recipes:
        del recipes[pn  + "-native"]

    # Regular recipes
    if ((pn in recipes and recipes[pn] < pv) or (pn not in recipes)):
        # Don't add git or svn if database contains regular versioning
        if pv == "git" or pv == "svn":
            try:
                latest_upgrade = RecipeUpgrade.objects.filter(
                                    recipe = recipe).order_by('-date')[0]
                if pv != latest_upgrade:
                    return
            except:
                pass

        recipes[pn] = pv

"""
    Returns a dictionary containing packages names and versions of
    the recipes the given commit.
"""
def get_commit_recipes(commit, repodir, layerdir):
    commit_recipes = {}
    layerdir_start = os.path.normpath(layerdir) + os.sep

    files = utils.runcmd("git log --name-only --format='%n' -n 1 " + commit, repodir)
    # Get files from within the commit
    for f in files.split("\n"):
        if f != "":
            fullpath = os.path.join(repodir, f)

            # Skip deleted files in commit
            if not os.path.exists(fullpath):
                continue

            (typename, _, filename) = recipeparse.detect_file_type(
                                        fullpath, layerdir_start)
            if typename == 'recipe':
                # Package name an version are taken directly from the filename
                (pn, pv) = recipeparse.split_recipe_fn(fullpath)
                insert_clean_pn(commit_recipes, pn, pv)

    return commit_recipes
 
"""
    Detects from a series of commits (usually from a single day),
    which are upgrades and inserts the new date in the RecipeUpgrade table.
"""    
def find_upgrades(commits, repodir, layerdir, logger):
    import re
    day_upgrades = {}
 
    # Take every commit from the current day and see if it contains the Upgrade keyword
    # or if a newer version is detected from the recipe name
    for commit in commits.split("\n"):
        if commit != "":
            commit_recipes = get_commit_recipes(commit, repodir, layerdir)
            title = utils.runcmd("git log --format='%s' -n 1 " + commit, repodir)

            for pn, pv in commit_recipes.iteritems():
                if re.search("[U|u]grade", title) or is_newer_version(pn, pv):
                    logger.debug("Detected upgrade in commit %s: %s" %
                                    (commit, title.strip()))
                    recipe = get_recipe(pn)
                    if not recipe:
                        continue
                    create_upgrade(commit, repodir, recipe, pv, logger)

"""
    Recreate upgrade history from the beign of Yocto Project
"""
def upgrade_history(logger):
    layername = settings.CORE_LAYER_NAME
    branchname = "master"

    layer = LayerItem.objects.filter(name__iexact = layername)[0]
    if not layer:
        self._logger.error("Poky layer does not exist")
        sys.exit(1)
    urldir = layer.get_fetch_dir()
    layerbranch = LayerBranch.objects.filter(layer__name__iexact =
                        layername).filter(branch__name__iexact =
                        branchname)[0]
    repodir = os.path.join(settings.LAYER_FETCH_DIR, urldir)
    layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

    inited = False

    # Starting date of the yocto project
    date = datetime.strptime("2010-06-11", "%Y-%m-%d")
    today = datetime.today()
    utils.runcmd("git checkout origin/master -f", repodir)

    # Clear all RecipeUpgrades
    RecipeUpgrade.objects.all().delete()

    # Get commits by day
    while (date - today).days != 0:
        logger.debug("Analysing commits for date: %s" % date)

        datestr = date.strftime("%Y-%m-%d")
        date_next = date + timedelta(days=1)
        date_nextstr = date_next.strftime("%Y-%m-%d")
        utils.runcmd("git branch -D " + datestr + " &> /dev/null", repodir)
        utils.runcmd("git checkout -b " + datestr, repodir)

        # Get commits for the current day
        commits = utils.runcmd("git log --since='" + datestr + "' --until='" +
                                date_nextstr + "' --format='%H' --reverse",
                                repodir)
        if len(commits) != 0:
            # Reset to the last commit of the day
            last_commit = commits.strip().split("\n")[-1]
            utils.runcmd("git reset --hard " + last_commit, repodir)
            if not inited:
                # Info about the recipes which existed when the project started
                initial_recipes(layerdir, date, logger)
                inited = True
            # Discover recipe upgrades
            find_upgrades(commits, repodir, layerdir, logger)
        utils.runcmd("git checkout origin/master -f", repodir)
        utils.runcmd("git branch -D " + datestr, repodir)

        date += timedelta(days=1)
    utils.runcmd("git checkout origin/master -f", repodir)

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    
    logger = utils.logger_create("HistoryUpdate")
    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    upgrade_history(logger)
