#!/usr/bin/env python3

# Get upstream information for recipes.
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
import optparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, load_recipes, \
        get_pv_type, get_logger, DryRunRollbackException
common_setup()
from layerindex import utils

utils.setup_django()
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
import settings

logger = get_logger("UpstreamHistory", settings)
fetchdir = settings.LAYER_FETCH_DIR
if not fetchdir:
    logger.error("Please set LAYER_FETCH_DIR in settings.py")
    sys.exit(1)

# setup bitbake path
bitbakepath = os.path.join(fetchdir, 'bitbake')
sys.path.insert(0, os.path.join(bitbakepath, 'lib'))

from layerindex.models import Recipe, LayerBranch
from rrs.models import RecipeUpstream, RecipeUpstreamHistory, MaintenancePlan

def set_regexes(d):
    """
        Utility function to set regexes to SPECIAL_PKGSUFFIX packages
        that don't have set it.

        For example: python-native use regex from python if don't have
        one set it.
    """

    variables = ('REGEX', 'REGEX_URI', 'GITTAGREGEX')

    if any(d.getVar(var, True) for var in variables):
        return

    suffixes = d.getVar('SPECIAL_PKGSUFFIX', True).split()
    prefixes = ['nativesdk-']

    special = list(suffixes)
    special.extend(prefixes)

    localdata = bb.data.createCopy(d)
    pn = localdata.getVar('PN', True)
    for s in special:
        if pn.find(s) != -1:
            if s in suffixes:
                pnstripped = pn.split(s)[0]
            else:
                pnstripped = pn.replace(s, '')

            localdata.setVar('OVERRIDES', "pn-" + pnstripped + ":" +
                    d.getVar('OVERRIDES', True))
            bb.data.update_data(localdata)

            for var in variables:
                new_value = localdata.getVar(var, True)
                if new_value is None:
                    continue

                d.setVar(var, new_value)
                logger.debug("%s: %s new value %s" % (pn, var,
                    d.getVar(var, True)))
            break

def get_upstream_info(layerbranch, recipe_data, result):
    from bb.utils import vercmp_string
    from oe.recipeutils import get_recipe_upstream_version, \
            get_recipe_pv_without_srcpv

    pn = recipe_data.getVar('PN', True)
    recipes = Recipe.objects.filter(layerbranch=layerbranch, pn=pn)
    if not recipes:
        logger.warning("%s: in layer branch %s not found." % \
                (pn, str(layerbranch)))
        return
    recipe = recipes[0]

    ru = RecipeUpstream()
    ru.recipe = recipe

    ru_info = None
    try:
        ru_info = get_recipe_upstream_version(recipe_data)
    except Exception as e:
        logger.exception("%s: in layer branch %s, %s" % (pn,
            str(layerbranch), str(e)))

    if ru_info is not None and ru_info['version']:
        ru.version = ru_info['version']
        ru.type = ru_info['type']
        ru.date = ru_info['datetime']

        pv, _, _ = get_recipe_pv_without_srcpv(recipe.pv, 
                get_pv_type(recipe.pv)) 
        upv, _, _ = get_recipe_pv_without_srcpv(ru_info['version'],
                get_pv_type(ru_info['version']))

        cmp_ver = vercmp_string(pv, upv)
        if cmp_ver == -1:
            ru.status = 'N' # Not update
        elif cmp_ver == 0:
            ru.status = 'Y' # Up-to-date
        elif cmp_ver == 1:
            ru.status = 'D' # Downgrade, need to review why
    else:
        ru.version = ''
        ru.type = 'M'
        ru.date = datetime.now()
        ru.status = 'U' # Unknown

    ru.no_update_reason = recipe_data.getVar('RECIPE_NO_UPDATE_REASON',
            True) or ''

    result.append((recipe, ru))

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    
    parser.add_option("--dry-run",
            help = "Do not write any data back to the database",
            action="store_true", dest="dry_run", default=False)

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)

    logger.debug("Starting upstream history...")

    try:
        maintplans = MaintenancePlan.objects.filter(updates_enabled=True)
        if not maintplans.exists():
            logger.error('No enabled maintenance plans found')
            sys.exit(1)

        origsyspath = sys.path

        for maintplan in maintplans:
            for item in maintplan.maintenanceplanlayerbranch_set.all():
                layerbranch = item.layerbranch
                with transaction.atomic():
                    sys.path = origsyspath

                    layer = layerbranch.layer
                    urldir = layer.get_fetch_dir()
                    repodir = os.path.join(fetchdir, urldir)
                    layerdir = os.path.join(repodir, layerbranch.vcs_subdir)

                    recipe_files = []
                    for recipe in layerbranch.recipe_set.all():
                        file = str(os.path.join(layerdir, recipe.full_path()))
                        recipe_files.append(file)

                    (tinfoil, d, recipes) = load_recipes(layerbranch, bitbakepath,
                            fetchdir, settings, logger,  recipe_files=recipe_files)

                    if not recipes:
                        tinfoil.shutdown()
                        continue

                    utils.setup_core_layer_sys_path(settings, layerbranch.branch.name)

                    for recipe_data in recipes:
                        set_regexes(recipe_data)

                    history = RecipeUpstreamHistory(start_date = datetime.now())

                    result = []
                    for recipe_data in recipes:
                        get_upstream_info(layerbranch, recipe_data, result)

                    history.end_date = datetime.now()
                    history.save()

                    for res in result:
                        (recipe, ru) = res

                        ru.history = history
                        ru.save()

                        logger.debug('%s: layer branch %s, pv %s, upstream (%s)' % (recipe.pn,
                            str(layerbranch), recipe.pv, str(ru)))

                    tinfoil.shutdown()
                    if options.dry_run:
                        raise DryRunRollbackException
    except DryRunRollbackException:
        pass
