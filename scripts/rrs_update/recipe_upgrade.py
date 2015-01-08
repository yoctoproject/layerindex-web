from datetime import datetime
from datetime import timedelta

import utils
import recipeparse

from django.db import transaction

from layerindex.models import Recipe
from rrs.models import Maintainer, RecipeUpgrade

"""
    Discovers the upgraded packages in the last day.
"""
def update_recipe_upgrades(layerbranch, repodir, layerdir, config_data, logger):
    today = datetime.today()
    yesterday = today - timedelta(days = 7)
    todaystr = today.strftime("%Y-%m-%d")
    yesterdaystr = yesterday.strftime("%Y-%m-%d")

    temp_branch = "recipe_upgrades"

    logger.debug("Check recent upgrades")

    utils.runcmd("git checkout origin/master ", repodir)

    # try to delete temp_branch if exists
    try:
        utils.runcmd("git branch -D " + temp_branch, repodir)
    except:
        pass


    transaction.enter_transaction_management()
    transaction.managed(True)
    commits = utils.runcmd("git log --since='" + yesterdaystr + "' --until='" +
                            todaystr + "' --format='%H' --reverse", repodir)
    for commit in commits.split("\n"):
        if commit != "":
            logger.debug("Analysing commit %s" % commit)
            commit_files = get_commit_files(commit, repodir, layerdir, logger)

            utils.runcmd("git branch " + temp_branch, repodir)
            utils.runcmd("git checkout " + temp_branch, repodir)
            utils.runcmd("git reset --hard " + commit, repodir)

            for path in commit_files:
                try:
                    envdata = bb.cache.Cache.loadDataFull(str(path), [],
                                config_data)
                    pn = envdata.getVar("PN", True)
                    pv = envdata.getVar("PV", True)
                except Exception as e:
                    logger.warn("Recipe %s couldn't be parsed, %s" %
                                (path, str(e)))
                    continue

                try:
                    recipe = Recipe.objects.get(layerbranch = layerbranch,
                            pn__exact = pn)
                except Exception as e:
                    # Most probably a native found
                    logger.warn("Recipe %s not found in database, %s" %
                                (pn, str(e)))
                    continue

                try:
                    latest_upgrade = RecipeUpgrade.objects.filter(
                            recipe = recipe).order_by('-commit_date')[0]
                    prev_pv = latest_upgrade.version
                except Exception as e:
                    prev_pv = None

                # if no previous version in database consider it an upgrade
                if not prev_pv or prev_pv != pv:
                    logger.debug("Detected upgrade for %s in commit %s." % (pn, commit))
                    create_upgrade(commit, repodir, recipe, pv, logger)

            utils.runcmd("git checkout origin/master ", repodir)
            utils.runcmd("git branch -D " + temp_branch, repodir)

    transaction.commit()
    transaction.leave_transaction_management()

"""
    Returns a list containing the fullpaths to the recipes from a commit.
"""
def get_commit_files(commit, repodir, layerdir, logger):
    commit_files = []
    layerdir_start = os.path.normpath(layerdir) + os.sep

    files = utils.runcmd("git log --name-only --format='%n' -n 1 " + commit,
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
                commit_files.append(fullpath)

    return commit_files

""" 
    Insert new entry in the RecipeUpgrade table.
"""
def create_upgrade(commit, repodir, recipe, pv, logger):
    from email.utils import parsedate_tz, mktime_tz
    info = utils.runcmd("git log  --format='%an;%ae;%ad;%cd' --date=rfc -n 1 " + commit,
                            destdir=repodir, logger=logger)

    maintainer_name = info.split(';')[0]
    maintainer_email = info.split(';')[1]
    author_date = info.split(';')[2]
    commit_date = info.split(';')[3]

    maintainer = get_maintainer(maintainer_name, maintainer_email, logger)
   
    title = utils.runcmd("git log --format='%s' -n 1 " + commit,
                            repodir, logger=logger)

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
    Gets maintainer with the given details from the database. 
    If the maintainer doesn't exist it will be created. 
"""
def get_maintainer(name, email, logger):
    try:
        maintainer = Maintainer.objects.get(name = name)
    except Maintainer.DoesNotExist:
        maintainer = Maintainer()
        maintainer.name = name
        maintainer.email = email
        maintainer.save()

        logger.debug("Create new maintainer %s: %s" %
                        (maintainer.name, maintainer.email))

    return maintainer
