#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Send email to maintainers about the current status of the recipes.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Author: Aníbal Limón <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import optparse
import logging
from collections import namedtuple

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_pv_type, get_logger
common_setup()
from layerindex import utils

utils.setup_django()
from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.template import Context, Template
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
import settings

from layerindex.models import LayerItem, LayerBranch, Recipe
from rrs.models import Maintainer, RecipeMaintainerHistory, RecipeMaintainer, \
    RecipeUpstream, RecipeUpstreamHistory, MaintenancePlan

logger = get_logger('UpstreamEmail', settings)


"""
    Send email with Recipes that need update.
"""
def send_email(maintplan, recipes, options):
    upgradable_count = 0
    no_upgradable_count = 0
    maintainers = Maintainer.objects.all().order_by("name")

    RecipeUpgradeLine = namedtuple('RecipeUpgradeLine', ['pn', 'pv', 'pv_upstream', 'maintainer', 'noupgradereason'])

    recipelines = []
    for m in maintainers:
        for recipe in recipes.keys():
            recipe_maintainer = recipes[recipe]['maintainer']
            recipe_upstream = recipes[recipe]['upstream']

            if m.id == recipe_maintainer.maintainer.id:
                pn_max_len = 20
                pv_max_len = 20
                name_max_len = 20
                reason_max_len = 30

                recipelines.append(RecipeUpgradeLine(recipe.pn, recipe.pv, recipe_upstream.version, m.name, recipe_upstream.no_update_reason))

                upgradable_count = upgradable_count + 1
                if recipe_upstream.no_update_reason:
                    no_upgradable_count = no_upgradable_count + 1


    commits = []
    fetchdir = settings.LAYER_FETCH_DIR
    for item in maintplan.maintenanceplanlayerbranch_set.all():
        layerbranch = item.layerbranch
        layer = layerbranch.layer
        urldir = layer.get_fetch_dir()
        repodir = os.path.join(fetchdir, urldir)
        # FIXME this assumes the correct branch is checked out
        topcommitdesc = utils.runcmd(['git', 'log', '-1', '--oneline'], repodir).strip()
        commits.append('%s: %s' % (layerbranch.layer.name, topcommitdesc))

    # Render the subject as a template (to allow a bit of flexibility)
    subject = options.subject or maintplan.email_subject
    subject_template = Template(subject)
    current_site = Site.objects.get_current()
    d = Context({
        'maintplan': maintplan,
        'site': current_site,
    })
    subject_content = subject_template.render(d)

    from_email = options._from or maintplan.email_from
    if options.to:
        to_email_list = options.to.split(';')
    elif maintplan.email_to:
        to_email_list = maintplan.email_to.split(';')
    else:
        to_email_list = []

    if not subject:
        logger.error('No subject specified in maintenance plan %s and none specified on command line' % maintplan.name)
        sys.exit(1)
    if not from_email:
        logger.error('No sender email address specified in maintenance plan %s and none specified on command line' % maintplan.name)
        sys.exit(1)
    if not to_email_list:
        logger.error('No recipient email address specified in maintenance plan %s and none specified on command line' % maintplan.name)
        sys.exit(1)

    plaintext = get_template('rrs/report_email.txt')
    site_url = 'http://' + current_site.domain + reverse('rrs_frontpage')
    d = {
        'maintplan': maintplan,
        'site': current_site,
        'site_url': site_url,
        'upgradable_count': (upgradable_count - no_upgradable_count),
        'total_upgradable_count': upgradable_count,
        'commits': commits,
        'recipelines': recipelines,
    }
    text_content = plaintext.render(d)

    msg = EmailMessage(subject_content, text_content, from_email, to_email_list)
    msg.send()

def main():
    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-p", "--plan",
            help="Specify maintenance plan to operate on (default is all plans that have updates enabled)",
            action="store", dest="plan", default=None)

    parser.add_option("-s", "--subject",
            action="store", dest="subject", help='Override email subject')
    parser.add_option("-f", "--from",
            action="store", dest="_from", help='Override sender address')
    parser.add_option("-t", "--to",
            action="store", dest="to", help='Override recipient address')
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    # get recipes for send email
    if options.plan:
        maintplans = MaintenancePlan.objects.filter(id=int(options.plan))
        if not maintplans.exists():
            logger.error('No maintenance plan with ID %s found' % options.plan)
            sys.exit(1)
    else:
        maintplans = MaintenancePlan.objects.filter(email_enabled=True)
        if not maintplans.exists():
            logger.error('No maintenance plans with email enabled were found')
            sys.exit(1)

    for maintplan in maintplans:
        recipes = {}
        for item in maintplan.maintenanceplanlayerbranch_set.all():
            layerbranch = item.layerbranch

            recipe_upstream_history = RecipeUpstreamHistory.get_last(layerbranch)
            if recipe_upstream_history is None:
                logger.warn('I don\'t have Upstream information yet, run update.py script')
                sys.exit(1)

            recipe_maintainer_history = RecipeMaintainerHistory.get_last(layerbranch)
            if recipe_maintainer_history is None:
                logger.warn('I don\'t have Maintainership information yet,' +
                        ' run rrs_maintainer_history.py script')
                sys.exit(1)

            for recipe in layerbranch.recipe_set.all():
                recipe_upstream_query = RecipeUpstream.objects.filter(recipe =
                        recipe, history = recipe_upstream_history)
                if recipe_upstream_query and recipe_upstream_query[0].status == 'N':
                    recipes[recipe] = {}

                    recipe_maintainer = RecipeMaintainer.objects.filter(recipe =
                            recipe, history = recipe_maintainer_history)[0]
                    recipes[recipe]['maintainer'] = recipe_maintainer
                    recipes[recipe]['upstream'] = recipe_upstream_query[0]

        send_email(maintplan, recipes, options)

if __name__ == "__main__":
    main()
