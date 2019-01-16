#!/usr/bin/env python3

# Standalone script which rebuilds the history of all the upgrades.
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Authors: Anibal Limon <anibal.limon@linux.intel.com>
#          Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import optparse
import logging
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_logger

common_setup()
from layerindex import utils

import git

utils.setup_django()
import settings

logger = get_logger("HistoryUpgrade", settings)
fetchdir = settings.LAYER_FETCH_DIR
bitbakepath = os.path.join(fetchdir, 'bitbake')
if not fetchdir:
    logger.error("Please set LAYER_FETCH_DIR in settings.py")
    sys.exit(1)


def run_internal(maintplanlayerbranch, commit, commitdate, options, logger, bitbake_map, initial=False):
    from layerindex.models import PythonEnvironment
    from rrs.models import Release
    if commitdate < maintplanlayerbranch.python3_switch_date:
        # Python 2
        if maintplanlayerbranch.python2_environment:
            cmdprefix = maintplanlayerbranch.python2_environment.get_command()
        else:
            cmdprefix = 'python'
        # Ensure we're using a bitbake version that is python 2 compatible
        if commitdate > datetime(2016, 5, 10):
            commitdate = datetime(2016, 5, 10)
    else:
        # Python 3
        if maintplanlayerbranch.python3_environment:
            cmdprefix = maintplanlayerbranch.python3_environment.get_command()
        else:
            cmdprefix = 'python3'

    bitbake_rev = utils.runcmd(['git', 'rev-list', '-1', '--before=%s' % str(commitdate), 'origin/master'],
                    bitbakepath, logger=logger)
    check_rev = bitbake_map.get(bitbake_rev, None)
    if check_rev:
        logger.debug('Preferring bitbake revision %s over %s' % (check_rev, bitbake_rev))
        bitbake_rev = check_rev

    cmd = '%s upgrade_history_internal.py %s %s' % (cmdprefix, maintplanlayerbranch.layerbranch.id, commit)
    if initial:
        release = Release.get_by_date(maintplanlayerbranch.plan, commitdate)
        if release:
            comment = 'Initial import at %s release start.' % release.name
        else:
            comment = 'Initial import at %s' % commit
        cmd += ' --initial="%s"' % comment
    if bitbake_rev:
        cmd += ' --bitbake-rev %s' % bitbake_rev
    if options.dry_run:
        cmd += ' --dry-run'
    if options.loglevel == logging.DEBUG:
        cmd += ' --debug'
    logger.debug('Running %s' % cmd)
    ret, output = utils.run_command_interruptible(cmd)
    if ret == 254:
        # Interrupted by user, break out of loop
        logger.info('Update interrupted, exiting')
        sys.exit(254)

"""
    Upgrade history handler.
"""
def upgrade_history(options, logger):
    from rrs.models import MaintenancePlan, RecipeUpgrade, Release, Milestone

    if options.plan:
        maintplans = MaintenancePlan.objects.filter(id=int(options.plan))
        if not maintplans.exists():
            logger.error('No maintenance plan with ID %s found' % options.plan)
            sys.exit(1)
    else:
        maintplans = MaintenancePlan.objects.filter(updates_enabled=True)
        if not maintplans.exists():
            logger.error('No enabled maintenance plans found')
            sys.exit(1)

    lockfn = os.path.join(fetchdir, "layerindex.lock")
    lockfile = utils.lock_file(lockfn)
    if not lockfile:
        logger.error("Layer index lock timeout expired")
        sys.exit(1)
    try:
        for maintplan in maintplans:
            # Check releases and milestones
            current = date.today()
            current_release = Release.get_by_date(maintplan, current)
            if current_release:
                current_milestone = Milestone.get_by_release_and_date(current_release, current)
                if not current_milestone:
                    logger.warning('%s: there is no milestone defined in the latest release (%s) that covers the current date, so up-to-date data will not be visible in the web interface.' % (maintplan, current_release))
            else:
                logger.warning('%s: there is no release defined that covers the current date, so up-to-date data will not be visible in the web interface.' % maintplan)

            for maintplanbranch in maintplan.maintenanceplanlayerbranch_set.all():
                layerbranch = maintplanbranch.layerbranch
                if options.fullreload and not options.dry_run:
                    RecipeUpgrade.objects.filter(recipe__layerbranch=layerbranch).delete()
                layer = layerbranch.layer
                urldir = layer.get_fetch_dir()
                repodir = os.path.join(fetchdir, urldir)
                layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

                if options.commit:
                    initial = False
                    since = options.commit
                    since_option = ['%s^..%s' % (options.commit, options.commit)]
                elif maintplanbranch.upgrade_rev and not options.fullreload:
                    initial = False
                    since = maintplanbranch.upgrade_date
                    since_option = ['%s..origin/master' % maintplanbranch.upgrade_rev]
                else:
                    initial = True
                    since = options.since
                    since_option = ['--since=%s' % since, 'origin/master']

                repo = git.Repo(repodir)
                if repo.bare:
                    logger.error('Repository %s is bare, not supported' % repodir)
                    continue

                commits = utils.runcmd(['git', 'log'] + since_option + ['--format=%H %ct', '--reverse'],
                                    repodir,
                                    logger=logger)
                commit_list = commits.split('\n')

                bitbake_map = {}
                # Filter out some bad commits
                bitbake_commits = utils.runcmd(['git', 'rev-list', 'fef18b445c0cb6b266cd939b9c78d7cbce38663f^..39780b1ccbd76579db0fc6fb9369c848a3bafa9d^'],
                                    bitbakepath,
                                    logger=logger)
                bitbake_commit_list = bitbake_commits.splitlines()
                for commit in bitbake_commit_list:
                    bitbake_map[commit] = '39780b1ccbd76579db0fc6fb9369c848a3bafa9d'

                if initial:
                    logger.debug("Adding initial upgrade history ....")

                    ct, ctepoch = commit_list.pop(0).split()
                    ctdate = datetime.fromtimestamp(int(ctepoch))
                    run_internal(maintplanbranch, ct, ctdate, options, logger, bitbake_map, initial=True)

                if layerbranch.vcs_subdir:
                    layersubdir_start = layerbranch.vcs_subdir
                    if not layersubdir_start.endswith('/'):
                        layersubdir_start += '/'
                else:
                    layersubdir_start = ''
                logger.debug("Adding upgrade history from %s to %s ..." % (since, datetime.today().strftime("%Y-%m-%d")))
                for item in commit_list:
                    if item:
                        ct, ctepoch = item.split()
                        ctdate = datetime.fromtimestamp(int(ctepoch))
                        commitobj = repo.commit(ct)
                        touches_recipe = False
                        for parent in commitobj.parents:
                            diff = parent.diff(commitobj)
                            for diffitem in diff:
                                if layersubdir_start and not (diffitem.a_path.startswith(layersubdir_start) or diffitem.b_path.startswith(layersubdir_start)):
                                    # Not in this layer, skip it
                                    continue
                                if diffitem.a_path.endswith(('.bb', '.inc')) or diffitem.b_path.endswith(('.bb', '.inc')):
                                    # We need to look at this commit
                                    touches_recipe = True
                                    break
                            if touches_recipe:
                                break
                        if not touches_recipe:
                            # No recipes in the layer changed in this commit
                            # NOTE: Whilst it's possible that a change to a class might alter what's
                            # in the recipe, we can ignore that since we are only concerned with actual
                            # upgrades which would always require some sort of change to the recipe
                            # or an include file, so we can safely skip commits that don't do that
                            logger.debug("Skipping commit %s" % ct)
                            continue
                        logger.debug("Analysing commit %s ..." % ct)
                        run_internal(maintplanbranch, ct, ctdate, options, logger, bitbake_map)
                        if not options.dry_run:
                            maintplanbranch.upgrade_rev = ct
                            maintplanbranch.upgrade_date = ctdate
                            maintplanbranch.save()
    finally:
        utils.unlock_file(lockfile)

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")

    # Starting date of the yocto project 1.6 release
    DEFAULT_SINCE_DATE = '2013-11-11'
    parser.add_option("-s", "--since",
            help="Specify initial date for importing recipe upgrades (default '%s')" % DEFAULT_SINCE_DATE,
            action="store", dest="since", default=DEFAULT_SINCE_DATE)

    parser.add_option("-c", "--commit",
            help="Specify a single commit to import (for debugging)",
            action="store", dest="commit", default='')

    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)

    parser.add_option("--dry-run",
            help = "Do not write any data back to the database",
            action="store_true", dest="dry_run", default=False)

    parser.add_option("--fullreload",
            help="Reload upgrade data from scratch",
            action="store_true", dest="fullreload", default=False)

    parser.add_option("-p", "--plan",
            help="Specify maintenance plan to operate on (default is all plans that have updates enabled)",
            action="store", dest="plan", default=None)

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    upgrade_history(options, logger)
