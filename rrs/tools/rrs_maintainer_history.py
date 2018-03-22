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
from rrs.models import MaintenancePlan, Maintainer, RecipeMaintainerHistory, RecipeMaintainer
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

"""
    Recreate Maintainership history from the beginning
"""
def maintainer_history(options, logger):
    maintplans = MaintenancePlan.objects.filter(updates_enabled=True)
    if not maintplans.exists():
        logger.error('No enabled maintenance plans found')
        sys.exit(1)

    no_maintainer, _ = Maintainer.objects.get_or_create(name='No maintainer')

    for maintplan in maintplans:
        for item in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = item.layerbranch
            urldir = str(layerbranch.layer.get_fetch_dir())
            repodir = os.path.join(settings.LAYER_FETCH_DIR, urldir)
            layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

            utils.runcmd("git checkout master -f", layerdir, logger=logger)
            maintainers_full_path = os.path.join(layerdir, MAINTAINERS_INCLUDE_PATH)
            if not os.path.exists(maintainers_full_path):
                logger.debug('No maintainers.inc for %s, skipping' % layerbranch)
                continue

            commits = utils.runcmd("git log --format='%H' --reverse --date=rfc " +
                    os.path.join(layerbranch.vcs_subdir, MAINTAINERS_INCLUDE_PATH), repodir, logger=logger)

            try:
                with transaction.atomic():
                    for commit in commits.strip().split("\n"):
                        if RecipeMaintainerHistory.objects.filter(sha1=commit):
                            continue

                        logger.debug("Analysing commit %s ..." % (commit))

                        (author_name, author_email, date, title) = \
                            get_commit_info(utils.runcmd("git show " + commit, repodir,
                                logger=logger), logger)

                        author = Maintainer.create_or_update(author_name, author_email)
                        rms = RecipeMaintainerHistory(title=title, date=date, author=author,
                                sha1=commit)
                        rms.save()

                        utils.runcmd("git checkout %s -f" % commit,
                                repodir, logger=logger)

                        lines = [line.strip() for line in open(maintainers_full_path)]
                        for line in lines:
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
                                rm.maintainer = no_maintainer
                                rm.history = rms
                                rm.save()
                                logger.debug("%s: Not found maintainer in commit %s set to 'No maintainer'." % \
                                                (recipe.pn, rms.sha1))

                        utils.runcmd("git checkout master -f", repodir, logger=logger)

                    # set new recipes to no maintainer if don't have one
                    rms = RecipeMaintainerHistory.get_last()
                    for recipe in layerbranch.recipe_set.all():
                        if not RecipeMaintainer.objects.filter(recipe = recipe, history = rms):
                            rm = RecipeMaintainer()
                            rm.recipe = recipe
                            rm.maintainer = no_maintainer
                            rm.history = rms
                            rm.save()
                            logger.debug("%s: New recipe not found maintainer set to 'No maintainer'." % \
                                            (recipe.pn))
                if options.dry_run:
                    raise DryRunRollbackException
            except DryRunRollbackException:
                pass

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
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
