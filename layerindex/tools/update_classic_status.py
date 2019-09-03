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

logger = utils.logger_create('LayerIndexComparisonUpdate')

class DryRunRollbackException(Exception):
    pass


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

    args = parser.parse_args()

    utils.setup_django()
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Update, ComparisonRecipeUpdate
    from django.db import transaction

    logger.setLevel(args.loglevel)

    layer = LayerItem.objects.filter(name=args.layer).first()
    if not layer:
        logger.error('Specified layer %s does not exist in database' % args.layer)
        sys.exit(1)

    layerbranch = layer.get_layerbranch(args.branch)
    if not layerbranch:
        logger.error("Specified branch %s does not exist in database" % args.branch)
        sys.exit(1)

    updateobj = None
    if args.update:
        updateobj = Update.objects.filter(id=int(args.update)).first()
        if not updateobj:
            logger.error("Specified update id %s does not exist in database" % args.update)
            sys.exit(1)

    if args.skip:
        skiplist = args.skip.split(',')
    else:
        skiplist = []
    try:
        with transaction.atomic():
            def recipe_pn_query(pn):
                return Recipe.objects.filter(layerbranch__branch__name='master').filter(pn=pn).order_by('-layerbranch__layer__index_preference')

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
