#!/usr/bin/env python

# Filters recipes only keep one by PN.
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
from common import common_setup, get_pv_type, get_logger, get_recipe_pv_without_srcpv
common_setup()
from layerindex import utils

utils.setup_django()
from django.db import transaction
import settings

logger = get_logger("UniqueRecipes", settings)
fetchdir = settings.LAYER_FETCH_DIR
if not fetchdir:
    logger.error("Please set LAYER_FETCH_DIR in settings.py")
    sys.exit(1)

# setup bitbake
bitbakepath = os.path.join(fetchdir, 'bitbake')
sys.path.insert(0, os.path.join(bitbakepath, 'lib'))
from bb.utils import vercmp_string

from layerindex.models import Recipe, LayerBranch

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    
    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    logger.info('Starting unique recipes ...')

    # only keep the major version of recipe
    logger.info('Starting remove of duplicate recipes only keep major version ...')
    with transaction.atomic():
        for layerbranch in LayerBranch.objects.all():
            recipes = {}

            for recipe in Recipe.objects.filter(layerbranch=layerbranch):
                recipes[recipe.pn] = None

            for pn in recipes.keys():
                for recipe in Recipe.objects.filter(layerbranch=layerbranch,
                        pn=pn):

                    if recipes[pn] is None:
                        recipes[pn] = recipe
                    else:
                        (ppv, _, _) = get_recipe_pv_without_srcpv(recipes[pn].pv,
                                get_pv_type(recipes[pn].pv))
                        (npv, _, _) = get_recipe_pv_without_srcpv(recipe.pv,
                                get_pv_type(recipe.pv))

                        if npv == 'git':
                            logger.debug("%s: Removed git recipe without version." \
                                    % (recipe.pn))
                            recipe.delete()
                        elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                            logger.debug("%s: Removed older recipe (%s), new recipe (%s)." \
                                    % (recipes[pn].pn, recipes[pn].pv, recipe.pv))
                            recipes[pn].delete()
                            recipes[pn] = recipe
                        else:
                            logger.debug("%s: Removed older recipe (%s), current recipe (%s)." \
                                    % (recipes[pn].pn, recipe.pv, recipes[pn].pv))
                            recipe.delete()
