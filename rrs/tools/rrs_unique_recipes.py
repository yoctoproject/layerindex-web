#!/usr/bin/env python

# Filters recipes only keep one by PN.
#
# To detect package versions of the recipes the script uses the name of the recipe.
# This doesn't work for some git and svn recipes, but is good enough for historical data.
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
from common import common_setup, update_repo, get_pv_type
common_setup()
from layerindex import utils

utils.setup_django()
from django.db import transaction
import settings

from layerindex.models import Recipe, LayerBranch

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    
    logger = utils.logger_create("HistoryUpgrade")
    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    # setup poky
    pokypath = update_repo(settings.LAYER_FETCH_DIR, 'poky', settings.POKY_REPO_URL,
        True, logger)
    sys.path.insert(0, os.path.join(pokypath, 'bitbake', 'lib'))
    sys.path.insert(0, os.path.join(pokypath, 'meta', 'lib'))
    from bb.utils import vercmp_string
    from oe.recipeutils import get_recipe_pv_without_srcpv

    logger.info('Starting unique recipes ...')

    transaction.enter_transaction_management()
    transaction.managed(True)

    # remove native, nativesdk cross and initial recipes
    logger.info('Starting remove of recipes with preffix or suffix ...')
    words = ['nativesdk-', '-native', '-cross', '-initial']
    for layerbranch in LayerBranch.objects.all():
        for recipe in Recipe.objects.filter(layerbranch=layerbranch):
            match = any(w in recipe.pn for w in words)
            if match:
                recipe.delete()
                logger.debug("%s: Removed found prefix or suffix." % recipe.pn)

    # only keep the major version of recipe
    logger.info('Starting remove of duplicate recipes only keep major version ...')
    for layerbranch in LayerBranch.objects.all():
        recipes = {}

        for recipe in Recipe.objects.filter(layerbranch=layerbranch):
            recipes[recipe.bpn] = None

        for bpn in recipes.keys():
            for recipe in Recipe.objects.filter(layerbranch=layerbranch,
                    bpn=bpn):

                if recipes[bpn] is None:
                    recipes[bpn] = recipe
                else:
                    (ppv, _, _) = get_recipe_pv_without_srcpv(recipes[bpn].pv,
                            get_pv_type(recipes[bpn].pv))
                    (npv, _, _) = get_recipe_pv_without_srcpv(recipe.pv,
                            get_pv_type(recipe.pv))

                    if npv == 'git':
                        logger.debug("%s: Removed git recipe without version." \
                                % (recipe.pn))
                        recipe.delete()
                    elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                        logger.debug("%s: Removed older recipe (%s), new recipe (%s)." \
                                % (recipes[bpn].pn, recipes[bpn].pv, recipe.pv))
                        recipes[bpn].delete()
                        recipes[bpn] = recipe
                    else:
                        logger.debug("%s: Removed older recipe (%s), current recipe (%s)." \
                                % (recipes[bpn].pn, recipe.pv, recipes[bpn].pv))
                        recipe.delete()


    transaction.commit()
    transaction.leave_transaction_management()
