# Internal script called by rrs_upgrade_history.py
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Authors: Anibal Limon <anibal.limon@linux.intel.com>
#          Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from datetime import datetime

import sys
import os
import optparse
import logging
import re
from distutils.version import LooseVersion

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_pv_type, load_recipes, \
        get_logger, DryRunRollbackException

common_setup()
from layerindex import utils, recipeparse
from layerindex.update_layer import split_recipe_fn

"""
    Store upgrade into RecipeUpgrade model.
"""
def _save_upgrade(recipe, pv, commit, title, info, logger):
    from email.utils import parsedate_tz, mktime_tz
    from rrs.models import Maintainer, RecipeUpgrade

    maintainer_name = info.split(';')[0]
    maintainer_email = info.split(';')[1]
    author_date = info.split(';')[2]
    commit_date = info.split(';')[3]

    maintainer = Maintainer.create_or_update(maintainer_name, maintainer_email)

    upgrade = RecipeUpgrade()
    upgrade.recipe = recipe
    upgrade.maintainer = maintainer
    upgrade.author_date = datetime.utcfromtimestamp(mktime_tz(
                                    parsedate_tz(author_date)))
    upgrade.commit_date = datetime.utcfromtimestamp(mktime_tz(
                                    parsedate_tz(commit_date)))
    upgrade.version = pv
    upgrade.sha1 = commit
    upgrade.title = title.strip()
    upgrade.save()

"""
    Create upgrade receives new recipe_data and cmp versions.
"""
def _create_upgrade(recipe_data, layerbranch, ct, title, info, logger, initial=False):
    from layerindex.models import Recipe
    from rrs.models import RecipeUpgrade
    from bb.utils import vercmp_string

    pn = recipe_data.getVar('PN', True)
    pv = recipe_data.getVar('PV', True)

    if '..' in pv or pv.endswith('.'):
        logger.warn('Invalid version for recipe %s in commit %s, ignoring' % (recipe_data.getVar('FILE', True), ct))
        return

    recipes = Recipe.objects.filter(pn=pn, layerbranch=layerbranch).order_by('id')
    if not recipes:
        logger.warn("%s: Not found in Layer branch %s." %
                    (pn, str(layerbranch)))
        return
    recipe = recipes[0]

    try:
        latest_upgrade = RecipeUpgrade.objects.filter(
                recipe = recipe).order_by('-commit_date')[0]
        prev_pv = latest_upgrade.version
    except KeyboardInterrupt:
        raise
    except:
        prev_pv = None

    if prev_pv is None:
        logger.debug("%s: Initial upgrade ( -> %s)." % (recipe.pn, pv))
        _save_upgrade(recipe, pv, ct, title, info, logger)
    else:
        from common import get_recipe_pv_without_srcpv

        (ppv, _, _) = get_recipe_pv_without_srcpv(prev_pv,
                get_pv_type(prev_pv))
        (npv, _, _) = get_recipe_pv_without_srcpv(pv,
                get_pv_type(pv))

        try:
            if npv == 'git':
                logger.debug("%s: Avoiding upgrade to unversioned git." % \
                        (recipe.pn)) 
            elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                if initial is True:
                    logger.debug("%s: Update initial upgrade ( -> %s)." % \
                            (recipe.pn, pv)) 
                    latest_upgrade.version = pv
                    latest_upgrade.save()
                else:
                    logger.debug("%s: detected upgrade (%s -> %s)" \
                            " in ct %s." % (pn, prev_pv, pv, ct))
                    _save_upgrade(recipe, pv, ct, title, info, logger)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error("%s: fail to detect upgrade (%s -> %s)" \
                            " in ct %s: %s" % (pn, prev_pv, pv, ct, str(e)))


"""
    Returns a list containing the fullpaths to the recipes from a commit.
"""
def _get_recipes_filenames(ct, repodir, layerdir, logger):
    import glob
    ct_files = []
    layerdir_start = os.path.normpath(layerdir) + os.sep

    files = utils.runcmd(['git', 'log', '--name-only', '--format=%n', '-n', '1', ct],
                            repodir, logger=logger)

    incdirs = []
    for f in files.split("\n"):
        if f != "":
            fullpath = os.path.join(repodir, f)
            # Skip deleted files in commit
            if not os.path.exists(fullpath):
                continue
            if not fullpath.startswith(layerdir_start):
                # Ignore files in repo that are outside of the layer
                continue
            (typename, _, filename) = recipeparse.detect_file_type(fullpath,
                                        layerdir_start)
            if typename == 'recipe':
                ct_files.append(fullpath)
            elif fullpath.endswith('.inc'):
                fpath = os.path.dirname(fullpath)
                if not fpath in incdirs:
                    incdirs.append(fpath)
    for fpath in incdirs:
        # Let's just assume that all .bb files next to a .inc need to be checked
        for f in glob.glob(os.path.join(fpath, '*.bb')):
            if not f in ct_files:
                ct_files.append(f)

    return ct_files


def checkout_layer_deps(layerbranch, commit, fetchdir, logger):
    """ Check out the repositories for a layer and its dependencies """
    # Some layers will be in the same repository, so we only want to check those out once
    done_repos = []
    def checkout_layer(lb, lcommit=None, lcommitdate=None, force=False):
        urldir = str(lb.layer.get_fetch_dir())
        repodir = os.path.join(fetchdir, urldir)
        if not repodir in done_repos:
            if not lcommit:
                lcommit = utils.runcmd(['git', 'rev-list', '-1', '--before=%s' % lcommitdate, 'origin/master'], repodir, logger=logger).strip()
            utils.checkout_repo(repodir, lcommit, logger, force)
            done_repos.append(repodir)

    # We "force" here because it's almost certain we'll be checking out a
    # different revision for the layer itself
    checkout_layer(layerbranch, commit, force=True)
    layer_urldir = str(layerbranch.layer.get_fetch_dir())
    layer_repodir = os.path.join(fetchdir, layer_urldir)
    commitdate = utils.runcmd(['git', 'show', '-s', '--format=%ci'], layer_repodir, logger=logger)

    for dep in layerbranch.get_recursive_dependencies():
        checkout_layer(dep, lcommitdate=commitdate)

    return commitdate


def generate_history(options, layerbranch_id, commit, logger):
    from layerindex.models import LayerBranch
    from rrs.models import Release
    layerbranch = LayerBranch.objects.get(id=layerbranch_id)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    layer = layerbranch.layer
    urldir = str(layer.get_fetch_dir())
    repodir = os.path.join(fetchdir, urldir)
    layerdir = os.path.join(repodir, str(layerbranch.vcs_subdir))

    commitdate = checkout_layer_deps(layerbranch, commit, fetchdir, logger)

    if options.initial:
        fns = None
    else:
        fns = _get_recipes_filenames(commit, repodir, layerdir, logger)
        if not fns:
            return

    # setup bitbake
    bitbakepath = os.path.join(fetchdir, 'bitbake')
    if options.bitbake_rev:
        bitbake_rev = options.bitbake_rev
        if not re.match('^[0-9a-f]{40}$', bitbake_rev):
            # Branch name, need to check out detached
            bitbake_rev = 'origin/%s' % bitbake_rev
    else:
        bitbake_rev = utils.runcmd(['git', 'rev-list', '-1', '--before=%s' % commitdate, 'origin/master'], bitbakepath, logger=logger).strip()
    utils.checkout_repo(bitbakepath, bitbake_rev, logger)
    sys.path.insert(0, os.path.join(bitbakepath, 'lib'))

    (tinfoil, d, recipes, tempdir) = load_recipes(layerbranch, bitbakepath,
                        fetchdir, settings, logger, recipe_files=fns,
                        nocheckout=True)
    try:

        if options.initial:
            title = options.initial
            info = 'No maintainer;;' + utils.runcmd(['git', 'log', '--format=%ad;%cd', '--date=rfc', '-n', '1', commit], destdir=repodir, logger=logger)
            recordcommit = ''
        else:
            title = utils.runcmd(['git', 'log', '--format=%s', '-n', '1', commit],
                                            repodir, logger=logger)
            info = utils.runcmd(['git', 'log', '--format=%an;%ae;%ad;%cd', '--date=rfc', '-n', '1', commit], destdir=repodir, logger=logger)
            recordcommit = commit

        try:
            with transaction.atomic():
                for recipe_data in recipes:
                    _create_upgrade(recipe_data, layerbranch, recordcommit, title,
                            info, logger, initial=options.initial)
                if options.dry_run:
                    raise DryRunRollbackException
        except DryRunRollbackException:
            pass

    finally:
        if tinfoil and hasattr(tinfoil, 'shutdown') and (LooseVersion(bb.__version__) > LooseVersion("1.27")):
            tinfoil.shutdown()
        utils.rmtree_force(tempdir)


if __name__=="__main__":
    logger = None
    try:
        utils.setup_django()
        from django.db import transaction
        import settings

        logger = get_logger("HistoryUpgrade", settings)

        parser = optparse.OptionParser(usage = """%prog [options] <layerbranchid> <commit>""")

        parser.add_option("-i", "--initial",
                help = "Do initial population of upgrade histories (and specify comment)",
                action="store", dest="initial", default='')

        parser.add_option("--bitbake-rev",
                help = "Use the specified bitbake revision instead of the most recent one at the metadata commit date",
                action="store", dest="bitbake_rev", default='')

        parser.add_option("-d", "--debug",
                help = "Enable debug output",
                action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)

        parser.add_option("--dry-run",
                help = "Do not write any data back to the database",
                action="store_true", dest="dry_run", default=False)

        options, args = parser.parse_args(sys.argv)

        logger.setLevel(options.loglevel)

        if len(args) < 2:
            logger.error('Please specify layerbranch ID')
            sys.exit(1)

        if len(args) < 3:
            logger.error('Please specify commit')
            sys.exit(1)

        generate_history(options, int(args[1]), args[2], logger)
    except KeyboardInterrupt:
        if logger:
            logger.info('Update interrupted, exiting')
        sys.exit(254)

