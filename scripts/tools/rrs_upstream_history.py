#!/usr/bin/env python

# Standalone script which rebuilds the history of upstream data based on
# Distrodata CSV reports
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from datetime import datetime

import sys
import os
import csv

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../lib')))
import utils
import re

utils.setup_django()
import settings
import optparse
import logging
import recipeparse

from layerindex.models import Recipe, LayerBranch, LayerItem
from rrs.models import RecipeUpstreamHistory, RecipeUpstream

fetchdir = settings.LAYER_FETCH_DIR
bitbakepath = os.path.join(fetchdir, 'bitbake')
sys.path.insert(0, os.path.join(bitbakepath, 'lib'))

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../rrs_update')))
from recipe_upstream import vercmp_string

file_regex = re.compile("report\.csv\.(?P<year>\d\d\d\d)-?(?P<month>\d\d)-?(?P<day>\d\d)")

def upstream_history(directory, logger):
    layername = settings.CORE_LAYER_NAME
    layer = LayerItem.objects.filter(name__iexact = layername)[0]
    if not layer:
        logger.error("%s layer does not exist" % layername)
        sys.exit(1)

    branchname = "master"
    branch = utils.get_branch(branchname)
    if not branch:
        logger.error("Specified branch %s is not valid" % branchname)
        sys.exit(1)

    layerbranch = LayerBranch.objects.filter(layer__name__iexact =
        layername).filter(branch__name__iexact = branchname)[0]

    files = os.listdir(directory)
    for f in files:
        s = file_regex.search(f)
        if not s:
            logger.warn("upstream_history: failed to parse %s" % f)
            continue

        datestr = s.group('year') + '/' + s.group('month') + '/' + s.group('day')

        history = RecipeUpstreamHistory()
        try:
            history.start_date = datetime.strptime(datestr, "%Y/%m/%d")
            history.end_date = history.start_date
        except:
            logger.warn("upstream_history: failed to format %s" % datestr)
            continue
        history.save()

        with open(os.path.join(directory, f), 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            try:
                for row in reader:
                    ru = RecipeUpstream()
                    try:
                        ru.recipe = Recipe.objects.get(layerbranch = layerbranch,
                                pn = row['PackageName'])
                    except:
                        logger.warn('layer %s recipe %s don\'t exist'
                                % (layername, row['PackageName']))
                        continue

                    ru.history = history
                    ru.version = row['UpVersion']
                    if ru.version == '':
                        ru.status = 'U' # Unknown
                    else:
                        try:
                            cmp_ver = vercmp_string(row['Version'], ru.version)
                            if cmp_ver == -1:
                                ru.status = 'N' # Not updated
                            elif cmp_ver == 0:
                                ru.status = 'Y' # Up-to-date
                            else:
                                ru.status = 'D' # Downgrade
                        except:
                            ru.status = 'U'
                            logger.error("vercmp_string: %s, %s - %s" % (row['PackageName'],
                                row['Version'], ru.version))

                    ru.type = 'A' # Automatic
                    ru.no_update_reason = row['NoUpgradeReason']
                    ru.date = ru.history.end_date
                    ru.save()
            except csv.Error as e:
                logger.error('file %s, line %d: %s' % (f, reader.line_num, e))

if __name__=="__main__":
    parser = optparse.OptionParser(usage = """%prog [options]""")
    
    parser.add_option("", "--directory",
            help = "Directory path where csv reports are stored",
            action="store", dest="directory")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel",
            default=logging.INFO)

    logger = utils.logger_create("UpstreamHistory")

    options, args = parser.parse_args(sys.argv)

    if not options.directory:
        logger.error("Please specify directory")
        sys.exit(1)

    logger.setLevel(options.loglevel)
    upstream_history(options.directory, logger)
