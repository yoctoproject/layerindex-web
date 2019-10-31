#!/usr/bin/env python3

#
# Copyright (C) 2019 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os.path


sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', 'layerindex')))

import argparse
import re
import glob
import utils
import logging
from datetime import date, datetime

class DryRunRollbackException(Exception):
    pass

logger = utils.logger_create('RRSDump')



def main():
    parser = argparse.ArgumentParser(description="Dump RRS upgrade info")
    parser.add_argument("plan",
            help="Specify maintenance plan to operate on")
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Hide all output except error messages')

    args = parser.parse_args()

    if args.debug:
        loglevel = logging.DEBUG
    elif args.quiet:
        loglevel = logging.WARNING
    else:
        loglevel = logging.INFO

    utils.setup_django()
    import settings
    from rrs.models import MaintenancePlan, Release, Milestone, RecipeUpgrade, RecipeSymbol
    import rrs.views
    from django.db import transaction

    logger.setLevel(loglevel)

    maintplan = MaintenancePlan.objects.filter(id=args.plan).first()
    if not maintplan:
        logger.error('No maintenance plan with id %s' % args.plan)
        sys.exit(1)

    release = maintplan.get_default_release()
    if not release:
        logger.error('No default release for maintenance plan %s' % maintplan)
        sys.exit(1)

    milestone = release.get_default_milestone()
    if not milestone:
        logger.error('No default milestone for release %s' % release)
        sys.exit(1)

    recipe_list = rrs.views._get_recipe_list(milestone)
    for r in recipe_list:
        recipesymbol = RecipeSymbol.objects.get(id=r.pk)
        print('* %s %s %s %s' % (r.name, r.version, r.upstream_version, r.upstream_status))
        details = []
        for ru in RecipeUpgrade.objects.filter(recipesymbol=recipesymbol).exclude(upgrade_type='M').order_by('group', '-commit_date', '-id'):
            details.append(rrs.views._get_recipe_upgrade_detail(maintplan, ru))
        details.sort(key=lambda s: rrs.views.RecipeUpgradeGroupSortItem(s.group), reverse=True)
        group = None
        for rud in details:
            if rud.group != group:
                print('    ---- %s ----' % rud.group.title)
                group = rud.group
            print('    - %s | %s | %s | %s | %s' % (rud.title, rud.version, rud.upgrade_type, rud.milestone_name, rud.date))

    sys.exit(0)


if __name__ == "__main__":
    main()
