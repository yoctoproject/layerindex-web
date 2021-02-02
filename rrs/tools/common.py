# Common functionality for RRS tools. 
#
# Copyright (C) 2015 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

import sys
import os
import logging

class DryRunRollbackException(Exception):
    pass


def common_setup():
    sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../')))
    sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '../../layerindex')))

    # We don't want git to prompt for any passwords (e.g. when accessing renamed/hidden github repos)
    os.environ['SSH_ASKPASS'] = ''
    os.environ['GIT_ASKPASS'] = ''
    os.environ['GIT_TERMINAL_PROMPT'] = '0'

def get_logger(name, settings):
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger(name)
    formatter = logging.Formatter("%(asctime)s: %(levelname)s: %(message)s")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    filename = os.path.join(settings.TOOLS_LOG_DIR, name)
    maxBytes = 8388608 # 8MB
    handler = RotatingFileHandler(filename, maxBytes=maxBytes)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.setLevel(logging.INFO)

    return logger

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

    # Exclude lib dir (likely to include templates)
    exclude_dirs = [os.path.join(layerdir, 'lib') + os.sep]
    # Exclude sub-layers
    for root, dirs, files in os.walk(layerdir):
        for d in dirs:
            if os.path.exists(os.path.join(root, d, 'conf', 'layer.conf')):
                exclude_dirs.append(os.path.join(root, d) + os.sep)

    recipe_files = []
    for root, dirs, files in os.walk(layerdir):
        if '.git' in dirs:
            dirs.remove('.git')

        # remove excluded dirs
        for d in dirs[:]:
            fullpath = os.path.join(root, d) + os.sep
            if fullpath in exclude_dirs:
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
            layer, layerbranch, logger)

    if recipe_files is None:
        recipe_files = get_recipe_files(layerdir)

    recipes = []
    for fn in recipe_files:
        try:
            logger.debug('Parsing %s' % fn)
            if hasattr(tinfoil, 'parse_recipe_file'):
                data = tinfoil.parse_recipe_file(fn, appends=False, config_data=d)
            else:
                data = bb.cache.Cache.loadDataFull(str(fn), [], d)

            try:
                pv = data.getVar('PV', True)
            except FetchError:
                data.setVar('SRCPV', '')

            recipes.append(data)
        except Exception as e:
            logger.error("%s: branch %s couldn't be parsed, %s" \
                    % (layerbranch, fn, str(e)))
            continue

    return (tinfoil, d, recipes, tempdir)

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
        regex = re.compile("(?P<pfx>(v|r|))(?P<ver>((\w+[\.\-_]*)+))")
        m = regex.match(pv)
        if m:
            pv = m.group('ver')
            pfx = m.group('pfx')

    return (pv, pfx, sfx)
