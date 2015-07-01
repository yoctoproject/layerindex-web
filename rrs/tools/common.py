# Common functionality for RRS tools. 
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

def common_setup():
    import sys, os
    sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../')))

def update_repo(fetchdir, repo_name, repo_url, pull, logger):
    import os
    from layerindex import utils, recipeparse

    path = os.path.join(fetchdir, repo_name)

    logger.info("Fetching %s from remote repository %s"
                    % (repo_name, repo_url))
    if not os.path.exists(path):
        out = utils.runcmd("git clone %s %s" % (repo_url, repo_name),
                fetchdir, logger = logger)
    elif pull == True:
        out = utils.runcmd("git pull", path, logger = logger)
    else:
        out = utils.runcmd("git fetch", path, logger = logger)

    return path
