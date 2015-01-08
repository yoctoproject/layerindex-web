#!/usr/bin/env python

# Insert a milestone in the database. Same effect can be achieved from the
# administrator area.
#
# Copyright (C) 2014 - 2015 Intel Corporation
# Author: Marius Avram <marius.avram@intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../lib')))
import utils
utils.setup_django()
import settings
from datetime import datetime
from django.db import IntegrityError
import optparse
import logging
from rrs.models import Milestone

logger = utils.logger_create('MilestoneCreation')

""" Adds milestone to database. """
def create_milestone(name, start, end):
    milestone = Milestone()
    milestone.name = name
    if start == "today":
        milestone.start_date = datetime.today()
    else:
        date = datetime.strptime(start, "%Y-%m-%d")
        if not date:
            logger.error("incorrect start date format")
            sys.exit(1)
        milestone.start_date = date
    date = datetime.strptime(end, "%Y-%m-%d")
    if not date:
        logger.erorr("incorrect end date format")
        sys.exit(1)
    milestone.end_date = date
    try:
        milestone.save()
    except IntegrityError, e:
        logger.error(e)
    logger.debug("Added milestone %s %s %s" % (name, milestone.start_date, milestone.end_date))

def main():
    parser = optparse.OptionParser(usage = """%prog [options]""")

    parser.add_option("-n", "--name",
            help = "Specify milestone name. Must be unique.",
            action="store", dest="name")
    parser.add_option("-s", "--start",
            help = "Specify milestone start. Default to today's date. Format:yyyy-MM-dd",
            action="store", dest="start", default='today')
    parser.add_option("-e", "--end",
            help = "Specify milestone end. Format:yyyy-MM-dd",
            action="store", dest="end")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)

    options, args = parser.parse_args(sys.argv)
    logger.setLevel(options.loglevel)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)
    

    if (not options.name) or (not options.end):
        logger.error('must specify at least name and ending date')
        parser.print_help()
        sys.exit(1)
    
    name = options.name
    start_date = options.start
    end_date = options.end
    
    create_milestone(name, start_date, end_date)

if __name__ == "__main__":
    main()
