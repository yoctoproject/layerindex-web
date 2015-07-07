#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Send email to maintainers about the current status of the recipes.
#
# Copyright (C) 2015 Intel Corporation
# Author: Aníbal Limón <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import optparse
import logging
from tabulate import tabulate

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, update_repo, get_pv_type, get_logger
common_setup()
from layerindex import utils

utils.setup_django()
from django.core.mail import EmailMessage
import settings

from layerindex.models import LayerItem, LayerBranch, Recipe
from rrs.models import Maintainer, RecipeMaintainerHistory, RecipeMaintainer, \
    RecipeUpstream, RecipeUpstreamHistory

logger = get_logger('UpstreamEmail', settings)

LAYERBRANCH_NAME = "master"

"""
    Send email with Recipes that need update.
"""
def send_email(recipes, repodir, options):
    header = """This mail was sent out by Recipe reporting system.

This message list those recipes which need to be upgraded. If maintainers
believe some of them needn't to upgrade this time, they can fill in
RECIPE_NO_UPDATE_REASON_pn-"xxx" in upstream_tracking files to ignore this
recipe remainder until newer upstream version was detected.

Example:
RECIPE_NO_UPDATE_REASON_pn-"xxx" = "Not upgrade to 2.0 is unstable"

You can check the detail information at:

http://packages.yoctoproject.org/

"""

    upgradable_count = 0
    no_upgradable_count = 0
    maintainers = Maintainer.objects.all().order_by("name")

    table_headers = ['Package', 'Version', 'Upstream version',
                'Maintainer', 'NoUpgradeReason']
    table = []
    for m in maintainers:
        for recipe in recipes.keys():
            recipe_maintainer = recipes[recipe]['maintainer']
            recipe_upstream = recipes[recipe]['upstream']

            if m.id == recipe_maintainer.maintainer.id:
                pn_max_len = 20
                pv_max_len = 20
                name_max_len = 20
                reason_max_len = 30

                pn = recipe.pn
                if len(pn) > pn_max_len:
                    pn = pn[0:pn_max_len - 3] + "..."

                pv = recipe.pv
                if len(pv) > pv_max_len:
                    pv = pv[0:pv_max_len - 3] + "..."

                pv_up = recipe_upstream.version
                if len(pv_up) > pv_max_len:
                    pv_up = pv_up[0:pv_max_len - 3] + "..."

                name = m.name
                if len(name) > name_max_len:
                    name = name[0:name_max_len - 3] + "..."

                reason = recipe_upstream.no_update_reason
                if len(reason) > reason_max_len:
                    reason = reason[0:reason_max_len - 3] + "..."

                table.append([pn, pv, pv_up, name, reason])

                upgradable_count = upgradable_count + 1
                if recipe_upstream.no_update_reason:
                    no_upgradable_count = no_upgradable_count + 1

    body = tabulate(table, table_headers, tablefmt="simple")

    footer = """
\nUpgradable count: %d\nUpgradable total count: %d\n
The based commit is:

%s
Any problem, please contact Anibal Limon <anibal.limon@intel.com> 
""" % ((upgradable_count - no_upgradable_count), upgradable_count, 
        utils.runcmd("git log -1", repodir))

    #
    subject = options.subject
    from_email = options._from
    to_email_list = options.to.split(';')
    text_content = header + body + footer

    msg = EmailMessage(subject, text_content, from_email, to_email_list)
    msg.send()

def main():
    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-l", "--layername",
            action="store", dest="layername", default=settings.CORE_LAYER_NAME)
    parser.add_option("-s", "--subject",
            action="store", dest="subject", default=settings.RRS_EMAIL_SUBJECT)
    parser.add_option("-f", "--from",
            action="store", dest="_from", default=settings.RRS_EMAIL_FROM)
    parser.add_option("-t", "--to",
            action="store", dest="to", default=settings.RRS_EMAIL_TO)
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")

    options, args = parser.parse_args(sys.argv)

    recipes = {}
    layer = LayerItem.objects.filter(name = options.layername)[0]

    # get recipes for send email
    layerbranch = layer.get_layerbranch(LAYERBRANCH_NAME)
    recipe_upstream_history = RecipeUpstreamHistory.get_last()
    if recipe_upstream_history is None:
        logger.warn('I don\'t have Upstream information yet, run update.py script')
        sys.exit(1)

    recipe_maintainer_history = RecipeMaintainerHistory.get_last()
    if recipe_maintainer_history is None:
        logger.warn('I don\'t have Maintainership information yet,' +
                ' run rrs_maintainer_history.py script')
        sys.exit(1)

    for recipe in Recipe.objects.filter(layerbranch = layerbranch):
        recipe_upstream_query = RecipeUpstream.objects.filter(recipe =
                recipe, history = recipe_upstream_history)
        if recipe_upstream_query and recipe_upstream_query[0].status == 'N':
            recipes[recipe] = {}

            recipe_maintainer = RecipeMaintainer.objects.filter(recipe =
                    recipe, history = recipe_maintainer_history)[0]
            recipes[recipe]['maintainer'] = recipe_maintainer
            recipes[recipe]['upstream'] = recipe_upstream_query[0]

    repodir = os.path.join(settings.LAYER_FETCH_DIR, layer.get_fetch_dir())

    send_email(recipes, repodir, options)

if __name__ == "__main__":
    main()
