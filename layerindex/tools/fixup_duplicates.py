#!/usr/bin/env python3

# Fix recipes that were moved out
#
# Copyright (C) 2017 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT


import sys
import os

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import optparse
import utils
import logging

class DryRunRollbackException(Exception):
    pass

logger = utils.logger_create('LayerIndexFixup')



def main():
    parser = optparse.OptionParser(
        usage = """
    %prog [options""")

    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")

    options, args = parser.parse_args(sys.argv)

    utils.setup_django()
    import settings
    from layerindex.models import Recipe
    from django.db import transaction

    logger.setLevel(options.loglevel)

    try:
        with transaction.atomic():
            #LayerBranch.objects.filter(layermaintainer__isnull=True).delete()
            #LayerItem.objects.filter(layerbranch__isnull=True).filter(classic=False).delete()
            #LayerItem.objects.filter(layerbranch__isnull=True).filter(classic=False).delete()
            for recipe in Recipe.objects.filter(filepath__startswith='../'):
                print('Deleting erroneous recipe %s %s' % (recipe.layerbranch, recipe))
                recipe.delete()

            if options.dryrun:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
