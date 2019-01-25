#!/usr/bin/env python

# Updates site name in Django database
#
# Copyright (C) 2019 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import utils

logger = utils.logger_create('LayerIndexComparisonUpdate')

class DryRunRollbackException(Exception):
    pass


def set_site_name(args):

    utils.setup_django()
    from django.contrib.sites.models import Site

    site = Site.objects.get_current()
    if not args.domain:
        if not site:
            print('No site object currently defined')
            return 1
        else:
            print('%s\t%s' % (site.domain, site.name))
            return 0

    if not site:
        site = Site()
    if args.domain:
        site.domain = args.domain
    if args.name:
        site.name = args.name
    site.save()

    return 0


def main():
    parser = argparse.ArgumentParser(description="Set site name tool",
                                     epilog="With no arguments, site domain/name will be printed.")

    parser.add_argument('domain', nargs='?', help='Site domain to set')
    parser.add_argument('name', nargs='?', help='Site descriptive name to set')

    args = parser.parse_args()

    ret = set_site_name(args)

    return ret


if __name__ == "__main__":
    try:
        ret = main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
