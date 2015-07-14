# Common functionality for RRS tools. 
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

def common_setup():
    import sys, os
    sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../')))

def get_logger(name, settings):
    import logging
    import os

    logger = logging.getLogger(name)
    formatter = logging.Formatter("%(asctime)s: %(levelname)s: %(message)s")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    filename = os.path.join(settings.TOOLS_LOG_DIR, name)
    maxBytes = 8388608 # 8MB
    handler = logging.handlers.RotatingFileHandler(filename,
                    maxBytes=maxBytes)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.setLevel(logging.INFO)

    return logger

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

def get_pv_type(pv):
    pv_type = ''
    if '+git' in pv:
        pv_type = 'git'
    elif '+svn' in pv:
        pv_type = 'svn'
    elif '+hg' in pv:
        pv_type = 'hg'

    return pv_type

def get_recipe_files(layerdir):
    from layerindex import recipeparse
    import os

    sublayer_dirs = []
    for root, dirs, files in os.walk(layerdir):
        for d in dirs:
            if os.path.exists(os.path.join(root, d, 'conf', 'layer.conf')):
                sublayer_dirs.append(os.path.join(root, d) + os.sep)

    recipe_files = []
    for root, dirs, files in os.walk(layerdir):
        if '.git' in dirs:
            dirs.remove('.git')

        # remove sublayer dirs
        for d in dirs[:]:
            fullpath = os.path.join(root, d) + os.sep
            if fullpath in sublayer_dirs:
                dirs.remove(d)

        for f in files:
            fullpath = os.path.join(root, f)
            (typename, _, filename) = recipeparse.detect_file_type(fullpath,
                    layerdir + os.sep)
            if typename == 'recipe':
                recipe_files.append(fullpath)
    return recipe_files

def load_recipes(layerbranch, bitbakepath, fetchdir, settings, logger,
        recipe_files=None, nocheckout=False):
    from layerindex import recipeparse
    from bb.fetch import FetchError

    try:
        (tinfoil, tempdir) = recipeparse.init_parser(settings,
                layerbranch.branch, bitbakepath, nocheckout=nocheckout,
                logger=logger)
    except recipeparse.RecipeParseError as e:
        logger.error(str(e))
        sys.exit(1)

    layer = layerbranch.layer
    urldir = str(layer.get_fetch_dir())
    repodir = os.path.join(fetchdir, urldir)
    layerdir = os.path.join(repodir, str(layerbranch.vcs_subdir))

    d = recipeparse.setup_layer(tinfoil.config_data, fetchdir, layerdir,
            layer, layerbranch)

    if recipe_files is None:
        recipe_files = get_recipe_files(layerdir)

    recipes = []
    for rp in recipe_files:
        try:
            data = bb.cache.Cache.loadDataFull(rp, [], d)
            try:
                pv = data.getVar('PV', True)
            except FetchError:
                data.setVar('SRCPV', '')

            recipes.append(data)
        except Exception as e:
            logger.error("%s: branch %s couldn't be parsed, %s" \
                    % (layerbranch, rp, str(e)))
            continue

    return (tinfoil, d, recipes)

# XXX: Copied from oe-core recipeutils to avoid import errors.
def get_recipe_pv_without_srcpv(pv, uri_type):
    """
    Get PV without SRCPV common in SCM's for now only
    support git.

    Returns tuple with pv, prefix and suffix.
    """
    import re

    pfx = ''
    sfx = ''

    if uri_type == 'git':
        git_regex = re.compile("(?P<pfx>(v|r|))(?P<ver>((\d+[\.\-_]*)+))(?P<sfx>(\+|)(git|)(r|)(AUTOINC|)(\+|))(?P<rev>.*)")
        m = git_regex.match(pv)

        if m:
            pv = m.group('ver')
            pfx = m.group('pfx')
            sfx = m.group('sfx')
    else:
        regex = re.compile("(?P<pfx>(v|r|))(?P<ver>((\d+[\.\-_]*)+))")
        m = regex.match(pv)
        if m:
            pv = m.group('ver')
            pfx = m.group('pfx')

    return (pv, pfx, sfx)
