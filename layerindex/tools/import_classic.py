#!/usr/bin/env python3

# Import OE-Classic recipe data into the layer index database
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT


import sys
import os.path

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import optparse
import logging
from datetime import datetime
import fnmatch
import re
import tempfile
import shutil
import utils
import recipeparse

logger = utils.logger_create('LayerIndexUpdate')


class DryRunRollbackException(Exception):
    pass


def update_recipe_file(tinfoil, data, path, recipe, layerdir_start, repodir):
    fn = str(os.path.join(path, recipe.filename))
    try:
        logger.debug('Updating recipe %s' % fn)
        if hasattr(tinfoil, 'parse_recipe_file'):
            envdata = tinfoil.parse_recipe_file(fn, appends=False, config_data=data)
        else:
            envdata = bb.cache.Cache.loadDataFull(fn, [], data)
        envdata.setVar('SRCPV', 'X')
        envdata.setVar('SRCDATE', 'X')
        envdata.setVar('SRCREV', 'X')
        envdata.setVar('OPIE_SRCREV', 'X')
        recipe.pn = envdata.getVar("PN", True)
        recipe.pv = envdata.getVar("PV", True)
        recipe.summary = envdata.getVar("SUMMARY", True)
        recipe.description = envdata.getVar("DESCRIPTION", True)
        recipe.section = envdata.getVar("SECTION", True)
        recipe.license = envdata.getVar("LICENSE", True)
        recipe.homepage = envdata.getVar("HOMEPAGE", True)
        recipe.provides = envdata.getVar("PROVIDES", True) or ""
        recipe.bbclassextend = envdata.getVar("BBCLASSEXTEND", True) or ""
        recipe.save()
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        if not recipe.pn:
            recipe.pn = recipe.filename[:-3].split('_')[0]
        logger.error("Unable to read %s: %s", fn, str(e))

def main():

    parser = optparse.OptionParser(
        usage = """
    %prog [options] <bitbakepath> <oeclassicpath>""")

    parser.add_option("-b", "--branch",
            help = "Specify branch to import into",
            action="store", dest="branch", default='oe-classic')
    parser.add_option("-l", "--layer",
            help = "Specify layer to import into",
            action="store", dest="layer", default='oe-classic')
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
    if len(args) < 3:
        logger.error('You must specify bitbakepath and oeclassicpath')
        parser.print_help()
        sys.exit(1)
    if len(args) > 3:
        logger.error('unexpected argument "%s"' % args[3])
        parser.print_help()
        sys.exit(1)

    utils.setup_django()
    import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Machine, BBAppend, BBClass
    from django.db import transaction

    logger.setLevel(options.loglevel)

    branch = utils.get_branch(options.branch)
    if not branch:
        logger.error("Specified branch %s is not valid" % options.branch)
        sys.exit(1)

    res = list(LayerItem.objects.filter(name=options.layer)[:1])
    if res:
        layer = res[0]
    else:
        layer = LayerItem()
        layer.name = options.layer
        layer.status = 'P'
        layer.layer_type = 'M'
        layer.summary = 'OE-Classic'
        layer.description = 'OpenEmbedded-Classic'
        layer.vcs_url =  'git://git.openembedded.org/openembedded'
        layer.vcs_web_url = 'http://cgit.openembedded.org/openembedded'
        layer.vcs_web_tree_base_url = 'http://cgit.openembedded.org/openembedded/tree/%path%'
        layer.vcs_web_file_base_url = 'http://cgit.openembedded.org/openembedded/tree/%path%'
        layer.comparison = True
        layer.save()

    layerbranch = layer.get_layerbranch(options.branch)
    if not layerbranch:
        # LayerBranch doesn't exist for this branch, create it
        layerbranch = LayerBranch()
        layerbranch.layer = layer
        layerbranch.branch = branch
        layerbranch.save()

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)
    fetchedrepos = []
    failedrepos = []

    bitbakepath = args[1]
    oeclassicpath = args[2]

    confparentdir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oe-classic'))
    os.environ['BBPATH'] = str("%s:%s" % (confparentdir, oeclassicpath))
    try:
        (tinfoil, tempdir) = recipeparse.init_parser(settings, branch, bitbakepath, nocheckout=True, classic=True, logger=logger)
    except recipeparse.RecipeParseError as e:
        logger.error(str(e))
        sys.exit(1)

    # Clear the default value of SUMMARY so that we can use DESCRIPTION instead if it hasn't been set
    tinfoil.config_data.setVar('SUMMARY', '')
    # Clear the default value of DESCRIPTION so that we can see where it's not set
    tinfoil.config_data.setVar('DESCRIPTION', '')
    # Clear the default value of HOMEPAGE ('unknown')
    tinfoil.config_data.setVar('HOMEPAGE', '')

    try:
        with transaction.atomic():
            layerdir_start = os.path.normpath(oeclassicpath) + os.sep
            layerrecipes = Recipe.objects.filter(layerbranch=layerbranch)
            layermachines = Machine.objects.filter(layerbranch=layerbranch)
            layerdistros = Distro.objects.filter(layerbranch=layerbranch)
            layerappends = BBAppend.objects.filter(layerbranch=layerbranch)
            layerclasses = BBClass.objects.filter(layerbranch=layerbranch)

            try:
                config_data_copy = recipeparse.setup_layer(tinfoil.config_data, fetchdir, oeclassicpath, layer, layerbranch, logger)
            except recipeparse.RecipeParseError as e:
                logger.error(str(e))
                sys.exit(1)

            layerrecipes.delete()
            layermachines.delete()
            layerdistros.delete()
            layerappends.delete()
            layerclasses.delete()
            for root, dirs, files in os.walk(oeclassicpath):
                if '.git' in dirs:
                    dirs.remove('.git')
                for f in files:
                    fullpath = os.path.join(root, f)
                    (typename, filepath, filename) = recipeparse.detect_file_type(fullpath, layerdir_start)
                    if typename == 'recipe':
                        recipe = ClassicRecipe()
                        recipe.layerbranch = layerbranch
                        recipe.filename = filename
                        recipe.filepath = filepath
                        update_recipe_file(tinfoil, config_data_copy, root, recipe, layerdir_start, oeclassicpath)
                        recipe.save()

            layerbranch.vcs_last_fetch = datetime.now()
            layerbranch.save()

            if options.dryrun:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass
    except:
        import traceback
        traceback.print_exc()
    finally:
        tinfoil.shutdown()

    shutil.rmtree(tempdir)
    sys.exit(0)


if __name__ == "__main__":
    main()
