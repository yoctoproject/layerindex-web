#!/usr/bin/env python

# Update cover info for OE-Classic / other distro recipes in OE layer index database
#
# Copyright (C) 2013, 2018 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import re
import utils
import logging
import json
from collections import OrderedDict

logger = utils.logger_create('LayerIndexComparisonUpdate')

class DryRunRollbackException(Exception):
    pass


def export(args, layerbranch, skiplist):
    from layerindex.models import ClassicRecipe
    from django.db.models import F
    jscoverlist = []
    # These shenanigans are necessary because values() order is not
    # guaranteed and we can't use values_list because that won't work with our
    # extra cover_layer field.
    fields = ['pn', 'cover_pn', 'cover_status', 'cover_comment', 'classic_category']
    recipequery = ClassicRecipe.objects.filter(layerbranch=layerbranch, deleted=False).order_by('pn').values(*fields, cover_layer=F('cover_layerbranch__layer__name'))
    fields.append('cover_layer') # need to add this after the call
    for recipe in recipequery:
        if recipe['pn'] in skiplist:
            logger.debug('Skipping %s' % recipe.pn)
            continue
        jscoverlist.append(OrderedDict([(k,recipe[k]) for k in fields]))
    jsdata = {'coverlist': jscoverlist}
    with open(args.export_data, 'w') as f:
        json.dump(jsdata, f, indent=4)


def main():

    parser = argparse.ArgumentParser(description='Comparison recipe cover status update tool')

    parser.add_argument('-b', '--branch',
            default='oe-classic',
            help='Specify branch to import into')
    parser.add_argument('-l', '--layer',
            default='oe-classic',
            help='Specify layer to import into')
    parser.add_argument('-u', '--update',
            help='Specify update record to link to')
    parser.add_argument('-n', '--dry-run',
            action='store_true',
            help='Don\'t write any data back to the database')
    parser.add_argument('-s', '--skip',
            help='Skip specified packages (comma-separated list, no spaces)')
    parser.add_argument('-d', '--debug',
            action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO,
            help='Enable debug output')
    parser.add_argument('-q', '--quiet',
            action='store_const', const=logging.ERROR, dest='loglevel',
            help='Hide all output except error messages')
    parser.add_argument('-i', '--import-data',
            metavar='FILE',
            help='Import cover status data')
    parser.add_argument('--ignore-missing',
            action='store_true',
            help='Do not warn if a recipe is missing when importing cover status data')
    parser.add_argument('--export-data',
            metavar='FILE',
            help='Export cover status data')

    args = parser.parse_args()

    utils.setup_django()
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Update, ComparisonRecipeUpdate
    from django.db import transaction

    logger.setLevel(args.loglevel)

    if args.import_data and args.export_data:
        logger.error('--i/--import-data and --export-data are mutually exclusive')
        sys.exit(1)

    layer = LayerItem.objects.filter(name=args.layer).first()
    if not layer:
        logger.error('Specified layer %s does not exist in database' % args.layer)
        sys.exit(1)

    layerbranch = layer.get_layerbranch(args.branch)
    if not layerbranch:
        logger.error("Specified branch %s does not exist in database" % args.branch)
        sys.exit(1)

    if args.skip:
        skiplist = args.skip.split(',')
    else:
        skiplist = []

    if args.export_data:
        export(args, layerbranch, skiplist)
        sys.exit(0)

    updateobj = None
    if args.update:
        updateobj = Update.objects.filter(id=int(args.update)).first()
        if not updateobj:
            logger.error("Specified update id %s does not exist in database" % args.update)
            sys.exit(1)

    try:
        with transaction.atomic():
            def recipe_pn_query(pn):
                return Recipe.objects.filter(layerbranch__branch__name='master').filter(pn=pn).order_by('-layerbranch__layer__index_preference')

            if args.import_data:
                recipequery = ClassicRecipe.objects.filter(layerbranch=layerbranch)
                layerbranches = {}
                with open(args.import_data, 'r') as f:
                    jsdata = json.load(f)
                for jsitem in jsdata['coverlist']:
                    changed = False
                    pn = jsitem.pop('pn')
                    recipe = recipequery.filter(pn=pn).first()
                    if not recipe:
                        if not args.ignore_missing:
                            logger.warning('Could not find recipe %s in %s' % (pn, layerbranch))
                        continue
                    cover_layer = jsitem.pop('cover_layer', None)
                    if cover_layer:
                        orig_layerbranch = recipe.cover_layerbranch
                        recipe.cover_layerbranch = layerbranches.get(cover_layer, None)
                        if recipe.cover_layerbranch is None:
                            recipe.cover_layerbranch = LayerBranch.objects.filter(branch__name='master', layer__name=cover_layer).first()
                            if recipe.cover_layerbranch is None:
                                logger.warning('Could not find cover layer %s in master branch' % cover_layer)
                            else:
                                layerbranches[cover_layer] = recipe.cover_layerbranch
                        if orig_layerbranch != recipe.cover_layerbranch:
                            changed = True
                    elif recipe.cover_layerbranch is not None:
                        recipe.cover_layerbranch = None
                        changed = True
                    valid_fields = [fld.name for fld in ClassicRecipe._meta.get_fields()]
                    for fieldname, value in jsitem.items():
                        if fieldname in valid_fields:
                            if getattr(recipe, fieldname) != value:
                                setattr(recipe, fieldname, value)
                                changed = True
                        else:
                            logger.error('Invalid field %s' % fieldname)
                            sys.exit(1)
                    if changed:
                        logger.info('Updating %s' % pn)
                        utils.validate_fields(recipe)
                        recipe.save()
            else:
                recipequery = ClassicRecipe.objects.filter(layerbranch=layerbranch).filter(deleted=False).filter(cover_status__in=['U', 'N'])
                for recipe in recipequery:
                    if recipe.pn in skiplist:
                        logger.debug('Skipping %s' % recipe.pn)
                        continue
                    updated = False
                    sanepn = recipe.pn.lower().replace('_', '-')
                    replquery = recipe_pn_query(sanepn)
                    found = False
                    for replrecipe in replquery:
                        logger.debug('Matched %s in layer %s' % (recipe.pn, replrecipe.layerbranch.layer.name))
                        recipe.cover_layerbranch = replrecipe.layerbranch
                        recipe.cover_pn = replrecipe.pn
                        recipe.cover_status = 'D'
                        recipe.cover_verified = False
                        recipe.save()
                        updated = True
                        found = True
                        break
                    if not found:
                        if layerbranch.layer.name == 'oe-classic':
                            if recipe.pn.endswith('-native') or recipe.pn.endswith('-nativesdk'):
                                searchpn, _, suffix = recipe.pn.rpartition('-')
                                replquery = recipe_pn_query(searchpn)
                                for replrecipe in replquery:
                                    if suffix in replrecipe.bbclassextend.split():
                                        logger.debug('Found BBCLASSEXTEND of %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                        recipe.cover_layerbranch = replrecipe.layerbranch
                                        recipe.cover_pn = replrecipe.pn
                                        recipe.cover_status = 'P'
                                        recipe.cover_verified = False
                                        recipe.save()
                                        updated = True
                                        found = True
                                        break
                                if not found and recipe.pn.endswith('-nativesdk'):
                                    searchpn, _, _ = recipe.pn.rpartition('-')
                                    replquery = recipe_pn_query('nativesdk-%s' % searchpn)
                                    for replrecipe in replquery:
                                        logger.debug('Found replacement %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                        recipe.cover_layerbranch = replrecipe.layerbranch
                                        recipe.cover_pn = replrecipe.pn
                                        recipe.cover_status = 'R'
                                        recipe.cover_verified = False
                                        recipe.save()
                                        updated = True
                                        found = True
                                        break
                        else:
                            if recipe.source_set.exists():
                                source0 = recipe.source_set.first()
                                if 'pypi.' in source0.url or 'pythonhosted.org' in source0.url:
                                    attempts = ['python3-%s' % sanepn, 'python-%s' % sanepn]
                                    if sanepn.startswith('py'):
                                        attempts.extend(['python3-%s' % sanepn[2:], 'python-%s' % sanepn[2:]])
                                    for attempt in attempts:
                                        replquery = recipe_pn_query(attempt)
                                        for replrecipe in replquery:
                                            logger.debug('Found match %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                            recipe.cover_layerbranch = replrecipe.layerbranch
                                            recipe.cover_pn = replrecipe.pn
                                            recipe.cover_status = 'D'
                                            recipe.cover_verified = False
                                            recipe.save()
                                            updated = True
                                            found = True
                                            break
                                        if found:
                                            break
                                    if not found:
                                        recipe.classic_category = 'python'
                                        recipe.save()
                                        updated = True
                                elif 'cpan.org' in source0.url:
                                    perlpn = sanepn
                                    if perlpn.startswith('perl-'):
                                        perlpn = perlpn[5:]
                                    if not (perlpn.startswith('lib') and perlpn.endswith('-perl')):
                                        perlpn = 'lib%s-perl' % perlpn
                                    replquery = recipe_pn_query(perlpn)
                                    for replrecipe in replquery:
                                        logger.debug('Found match %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                        recipe.cover_layerbranch = replrecipe.layerbranch
                                        recipe.cover_pn = replrecipe.pn
                                        recipe.cover_status = 'D'
                                        recipe.cover_verified = False
                                        recipe.save()
                                        updated = True
                                        found = True
                                        break
                                    if not found:
                                        recipe.classic_category = 'perl'
                                        recipe.save()
                                        updated = True
                                elif 'kde.org' in source0.url or 'github.com/KDE' in source0.url:
                                    recipe.classic_category = 'kde'
                                    recipe.save()
                                    updated = True
                            if not found:
                                if recipe.pn.startswith('R-'):
                                    recipe.classic_category = 'R'
                                    recipe.save()
                                    updated = True
                                elif recipe.pn.startswith('rubygem-'):
                                    recipe.classic_category = 'ruby'
                                    recipe.save()
                                    updated = True
                                elif recipe.pn.startswith('jdk-'):
                                    sanepn = sanepn[4:]
                                    replquery = recipe_pn_query(sanepn)
                                    for replrecipe in replquery:
                                        logger.debug('Found match %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                        recipe.cover_layerbranch = replrecipe.layerbranch
                                        recipe.cover_pn = replrecipe.pn
                                        recipe.cover_status = 'D'
                                        recipe.cover_verified = False
                                        recipe.save()
                                        updated = True
                                        found = True
                                        break
                                    recipe.classic_category = 'java'
                                    recipe.save()
                                    updated = True
                                elif recipe.pn.startswith('golang-'):
                                    if recipe.pn.startswith('golang-github-'):
                                        sanepn = 'go-' + sanepn[14:]
                                    else:
                                        sanepn = 'go-' + sanepn[7:]
                                    replquery = recipe_pn_query(sanepn)
                                    for replrecipe in replquery:
                                        logger.debug('Found match %s to cover %s in layer %s' % (replrecipe.pn, recipe.pn, replrecipe.layerbranch.layer.name))
                                        recipe.cover_layerbranch = replrecipe.layerbranch
                                        recipe.cover_pn = replrecipe.pn
                                        recipe.cover_status = 'D'
                                        recipe.cover_verified = False
                                        recipe.save()
                                        updated = True
                                        found = True
                                        break
                                    recipe.classic_category = 'go'
                                    recipe.save()
                                    updated = True
                                elif recipe.pn.startswith('gnome-'):
                                    recipe.classic_category = 'gnome'
                                    recipe.save()
                                    updated = True
                                elif recipe.pn.startswith('perl-'):
                                    recipe.classic_category = 'perl'
                                    recipe.save()
                                    updated = True
                if updated and updateobj:
                    rupdate, _ = ComparisonRecipeUpdate.objects.get_or_create(update=updateobj, recipe=recipe)
                    rupdate.link_updated = True
                    rupdate.save()

            if args.dry_run:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
