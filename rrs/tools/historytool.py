#!/usr/bin/env python3

# RRS Upstream history export/import tool
#
# Copyright (C) 2019 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import json
import argparse
import logging
from datetime import date, datetime

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', 'layerindex')))

import utils

class DryRunRollbackException(Exception):
    pass

logger = utils.logger_create('RrsExport')


def rrs_export(args):
    utils.setup_django()
    import settings
    from rrs.models import RecipeUpstreamHistory, RecipeUpstream

    class DatetimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return super(DatetimeEncoder, self).default(obj)

    # FIXME this doesn't export the layerbranch associated with the recipe (since it
    # was intended to export from the original forked RRS which was OE-Core only)
    data = {}
    data['recipeupstreamhistory'] = []
    for hist in RecipeUpstreamHistory.objects.all():
        histdata = {}
        histdata['start_date'] = hist.start_date
        histdata['end_date'] = hist.end_date
        upstreamsdata = []
        for upstream in hist.recipeupstream_set.all():
            upstreamdata = {}
            upstreamdata['recipe'] = upstream.recipe.pn
            upstreamdata['version'] = upstream.version
            upstreamdata['type'] = upstream.type
            upstreamdata['status'] = upstream.status
            upstreamdata['no_update_reason'] = upstream.no_update_reason
            upstreamdata['date'] = upstream.date
            upstreamsdata.append(upstreamdata)
        histdata['upstreams'] = upstreamsdata
        data['recipeupstreamhistory'].append(histdata)

    with open(args.outfile, 'w') as f:
        json.dump(data, f, cls=DatetimeEncoder, indent=4)

    return 0


def rrs_import(args):
    utils.setup_django()
    import settings
    from django.db import transaction
    from rrs.models import RecipeUpstreamHistory, RecipeUpstream
    from layerindex.models import Recipe

    core_layer = utils.get_layer(settings.CORE_LAYER_NAME)
    if not core_layer:
        logger.error('Unable to find core layer %s' % settings.CORE_LAYER_NAME)
        return 1
    core_layerbranch = core_layer.get_layerbranch('master')
    if not core_layerbranch:
        logger.error('Unable to find branch master of layer %s' % core_layerbranch.name)
        return 1

    layerbranch = core_layerbranch
    try:
        with transaction.atomic():
            with open(args.infile, 'r') as f:
                data = json.load(f)
                for item, itemdata in data.items():
                    if item == 'recipeupstreamhistory':
                        for histdata in itemdata:
                            ruh = RecipeUpstreamHistory()
                            ruh.start_date = histdata['start_date']
                            ruh.end_date = histdata['end_date']
                            ruh.layerbranch = layerbranch
                            ruh.save()
                            for upstreamdata in histdata['upstreams']:
                                ru = RecipeUpstream()
                                ru.history = ruh
                                pn = upstreamdata['recipe']
                                recipe = Recipe.objects.filter(layerbranch=layerbranch, pn=pn).first()
                                if not recipe:
                                    logger.warning('Could not find recipe %s in layerbranch %s' % (pn, layerbranch))
                                    continue
                                ru.recipe = recipe
                                ru.version = upstreamdata['version']
                                ru.type = upstreamdata['type']
                                ru.status = upstreamdata['status']
                                ru.no_update_reason = upstreamdata['no_update_reason']
                                ru.date = upstreamdata['date']
                                ru.save()

            if args.dry_run:
                raise DryRunRollbackException
    except DryRunRollbackException:
        pass

    return 0


def rrs_remove_duplicates(args):
    utils.setup_django()
    import settings
    from django.db import transaction
    from rrs.models import RecipeUpstreamHistory
    from layerindex.models import Recipe

    core_layer = utils.get_layer(settings.CORE_LAYER_NAME)
    if not core_layer:
        logger.error('Unable to find core layer %s' % settings.CORE_LAYER_NAME)
        return 1
    core_layerbranch = core_layer.get_layerbranch('master')
    if not core_layerbranch:
        logger.error('Unable to find branch master of layer %s' % core_layerbranch.name)
        return 1

    try:
        with transaction.atomic():
            for row in RecipeUpstreamHistory.objects.filter(layerbranch=core_layerbranch).order_by('-id'):
                if RecipeUpstreamHistory.objects.filter(layerbranch=row.layerbranch, start_date=row.start_date).count() > 1:
                    logger.info('Deleting duplicate %d' % row.id)
                    row.delete()
            if args.dry_run:
                raise DryRunRollbackException
    except DryRunRollbackException:
        pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="Recipe Reporting System import/export tool",
                                        epilog="Use %(prog)s <subcommand> --help to get help on a specific command")
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Hide all output except error messages')

    subparsers = parser.add_subparsers(title='subcommands', metavar='<subcommand>')
    subparsers.required = True

    parser_export = subparsers.add_parser('export',
                                            help='Export RRS history data',
                                          description='Exports RRS upstream history')
    parser_export.add_argument('outfile', help='Output file (.json)')
    parser_export.set_defaults(func=rrs_export)

    parser_import = subparsers.add_parser('import',
                                            help='Import RRS history data',
                                          description='Imports RRS upstream history')
    parser_import.add_argument('infile', help='Input file (.json)')
    parser_import.add_argument('-n', '--dry-run', action='store_true', help='Dry-run (do not commit changes back to database)')
    parser_import.set_defaults(func=rrs_import)

    parser_duplicates = subparsers.add_parser('remove-duplicates',
                                            help='Remove duplicate RRS history data',
                                          description='Remove duplicate RRS upstream history')
    parser_duplicates.add_argument('-n', '--dry-run', action='store_true', help='Dry-run (do not commit changes back to database)')
    parser_duplicates.set_defaults(func=rrs_remove_duplicates)

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)

    ret = args.func(args)

    return ret


if __name__ == "__main__":
    try:
        ret = main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
