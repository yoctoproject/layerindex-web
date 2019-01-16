#!/usr/bin/env python3

# Standalone script which rebuilds the history of maintainership
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import optparse
import logging

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_logger, DryRunRollbackException
common_setup()
from layerindex import utils, recipeparse

utils.setup_django()
from django.db import transaction
import settings

from layerindex.models import Recipe, LayerBranch, LayerItem
from rrs.models import MaintenancePlan, Maintainer, RecipeMaintainerHistory, RecipeMaintainer, RecipeMaintenanceLink
from django.core.exceptions import ObjectDoesNotExist

# FIXME we shouldn't be hardcoded to expect RECIPE_MAINTAINER to be set in this file,
# as it may be in the recipe in future
MAINTAINERS_INCLUDE_PATH = 'conf/distro/include/maintainers.inc'


"""
    Try to get recipe maintainer from line, if not found return None
"""
def get_recipe_maintainer(line, logger):
    import re
    regex = re.compile('^RECIPE_MAINTAINER_pn-(?P<pn>.*)\s=\s"(?P<name>.+) <(?P<email>.*)>"$')

    match = regex.search(line)
    if match:
        return (match.group('pn'), match.group('name'), match.group('email'))
    else:
        logger.debug("line (%s) don\'t match" % (line))
        return None

"""
    Get commit information from text.
    Returns author_name, author_email, date and title.
"""
def get_commit_info(info, logger):
    import re
    from datetime import datetime
    from email.utils import parsedate_tz, mktime_tz

    author_regex = re.compile("^Author: (?P<name>.*) <(?P<email>.*)>$")
    date_regex = re.compile("^Date:   (?P<date>.*)$")
    title_regex = re.compile("^    (?P<title>.*)$")

    lines = info.split('\n')

    author_name = author_regex.search(lines[1]).group('name')
    author_email = author_regex.search(lines[1]).group('email')
    date_str = date_regex.search(lines[2]).group('date')
    date = datetime.utcfromtimestamp(mktime_tz(parsedate_tz(date_str)))
    title = title_regex.search(lines[4]).group('title')

    return (author_name, author_email, date, title)


def maintainers_inc_history(options, logger, maintplan, layerbranch, repodir, layerdir):
    utils.checkout_layer_branch(layerbranch, repodir, logger=logger)

    maintainers_full_path = os.path.join(layerdir, MAINTAINERS_INCLUDE_PATH)
    if not os.path.exists(maintainers_full_path):
        logger.warning('Maintainer style is maintainers.inc for plan %s but no maintainers.inc exists in for %s' % (maintplan, layerbranch))
        return

    logger.debug('Checking maintainers.inc history for %s' % layerbranch)

    commits = utils.runcmd(['git', 'log', '--format=%H', '--reverse', '--date=rfc', 'origin/master',
                        os.path.join(layerbranch.vcs_subdir, MAINTAINERS_INCLUDE_PATH)],
                        repodir, logger=logger)

    no_maintainer, _ = Maintainer.objects.get_or_create(name='No maintainer')

    try:
        with transaction.atomic():
            for commit in commits.strip().split("\n"):
                if RecipeMaintainerHistory.objects.filter(layerbranch=layerbranch, sha1=commit):
                    continue

                logger.debug("Analysing commit %s ..." % (commit))

                (author_name, author_email, date, title) = \
                    get_commit_info(utils.runcmd(['git', 'show', commit], repodir,
                        logger=logger), logger)

                author = Maintainer.create_or_update(author_name, author_email)
                rms = RecipeMaintainerHistory(title=title, date=date, author=author,
                        sha1=commit, layerbranch=layerbranch)
                rms.save()

                utils.runcmd(['git', 'checkout', commit, '-f'],
                        repodir, logger=logger)

                with open(maintainers_full_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        res = get_recipe_maintainer(line, logger)
                        if res:
                            (pn, name, email) = res
                            qry = Recipe.objects.filter(pn = pn, layerbranch = layerbranch)

                            if qry:
                                m = Maintainer.create_or_update(name, email)

                                rm = RecipeMaintainer()
                                rm.recipe = qry[0]
                                rm.maintainer = m
                                rm.history = rms
                                rm.save()

                                logger.debug("%s: Change maintainer to %s in commit %s." % \
                                        (pn, m.name, commit))
                            else:
                                logger.debug("%s: Not found in %s." % \
                                        (pn, layerbranch))

                # set missing recipes to no maintainer
                for recipe in layerbranch.recipe_set.all():
                    if not RecipeMaintainer.objects.filter(recipe = recipe, history = rms):
                        rm = RecipeMaintainer()
                        rm.recipe = recipe
                        link_maintainer = RecipeMaintenanceLink.link_maintainer(recipe.pn, rms)
                        if link_maintainer:
                            rm.maintainer = link_maintainer.maintainer
                        else:
                            rm.maintainer = no_maintainer
                        rm.history = rms
                        rm.save()
                        if link_maintainer:
                            logger.debug("%s: linked to maintainer for %s" % (recipe.pn, link_maintainer.recipe.pn))
                        else:
                            logger.debug("%s: Not found maintainer in commit %s set to 'No maintainer'." % \
                                            (recipe.pn, rms.sha1))

            # set new recipes to no maintainer if don't have one
            rms = RecipeMaintainerHistory.get_last(layerbranch)
            for recipe in layerbranch.recipe_set.all():
                if not RecipeMaintainer.objects.filter(recipe = recipe, history = rms):
                    rm = RecipeMaintainer()
                    rm.recipe = recipe
                    link_maintainer = RecipeMaintenanceLink.link_maintainer(recipe.pn, rms)
                    if link_maintainer:
                        rm.maintainer = link_maintainer.maintainer
                    else:
                        rm.maintainer = no_maintainer
                    rm.history = rms
                    rm.save()
                    if link_maintainer:
                        logger.debug("%s: New recipe linked to maintainer for %s" % (recipe.pn, link_maintainer.recipe.pn))
                    else:
                        logger.debug("%s: New recipe not found maintainer set to 'No maintainer'." % \
                                    (recipe.pn))
        if options.dry_run:
            raise DryRunRollbackException
    except DryRunRollbackException:
        pass

"""
    Recreate Maintainership history from the beginning
"""
def maintainer_history(options, logger):
    fetchdir = settings.LAYER_FETCH_DIR
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
            for item in maintplan.maintenanceplanlayerbranch_set.all():
                layerbranch = item.layerbranch
                if options.fullreload and not options.dry_run:
                    RecipeMaintainerHistory.objects.filter(layerbranch=layerbranch).delete()
                urldir = str(layerbranch.layer.get_fetch_dir())
                repodir = os.path.join(fetchdir, urldir)
                layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

                if maintplan.maintainer_style == 'I':
                    # maintainers.inc
                    maintainers_inc_history(options, logger, maintplan, layerbranch, repodir, layerdir)
                elif maintplan.maintainer_style == 'L':
                    # Layer-wide, don't need to do anything
                    logger.debug('Skipping maintainer processing for %s - plan %s maintainer style is layer-wide' % (layerbranch, maintplan))
                else:
                    raise Exception('Unknown maintainer style %s for maintenance plan %s' % (maintplan.maintainer_style, maintplan))
    finally:
        utils.unlock_file(lockfile)

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")

    parser.add_option("-p", "--plan",
            help="Specify maintenance plan to operate on (default is all plans that have updates enabled)",
            action="store", dest="plan", default=None)

    parser.add_option("--fullreload",
            help="Reload upgrade data from scratch",
            action="store_true", dest="fullreload", default=False)

    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel",
            default=logging.INFO)

    parser.add_option("--dry-run",
            help = "Do not write any data back to the database",
            action="store_true", dest="dry_run", default=False)

    logger = get_logger("MaintainerUpdate", settings)
    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    maintainer_history(options, logger)
