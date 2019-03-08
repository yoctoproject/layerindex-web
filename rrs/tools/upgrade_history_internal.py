# Internal script called by rrs_upgrade_history.py
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Authors: Anibal Limon <anibal.limon@linux.intel.com>
#          Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import optparse
import logging
import re
from distutils.version import LooseVersion
import git
from datetime import datetime
import calendar
from email.utils import parsedate_tz

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))
from common import common_setup, get_pv_type, load_recipes, \
        get_logger, DryRunRollbackException

common_setup()
from layerindex import utils, recipeparse
from layerindex.update_layer import split_recipe_fn


def rfc2822_time_to_utc_datetime(ds):
    tt = parsedate_tz(ds)
    if tt is None:
        return None
    timestamp = calendar.timegm(tt) - tt[9]
    return datetime.utcfromtimestamp(timestamp)


"""
    Store upgrade into RecipeUpgrade model.
"""
def _save_upgrade(recipesymbol, layerbranch, pv, commit, title, info, filepath, logger, upgrade_type=None):
    from rrs.models import Maintainer, RecipeUpgrade, RecipeSymbol

    maintainer_name = info.split(';')[0]
    maintainer_email = info.split(';')[1]
    author_date = info.split(';')[2]
    commit_date = info.split(';')[3]

    maintainer = Maintainer.create_or_update(maintainer_name, maintainer_email)

    upgrade = RecipeUpgrade()
    upgrade.recipesymbol = recipesymbol
    upgrade.maintainer = maintainer
    upgrade.author_date = rfc2822_time_to_utc_datetime(author_date)
    upgrade.commit_date = rfc2822_time_to_utc_datetime(commit_date)
    upgrade.version = pv
    upgrade.sha1 = commit
    upgrade.title = title.strip()
    upgrade.filepath = filepath
    if upgrade_type:
        upgrade.upgrade_type = upgrade_type
    upgrade.save()

"""
    Create upgrade receives new recipe_data and cmp versions.
"""
def _create_upgrade(recipe_data, layerbranch, ct, title, info, filepath, logger, initial=False):
    from rrs.models import RecipeUpgrade, RecipeSymbol
    from bb.utils import vercmp_string

    pn = recipe_data.getVar('PN', True)
    pv = recipe_data.getVar('PV', True)

    if '..' in pv or pv.endswith('.'):
        logger.warn('Invalid version for recipe %s in commit %s, ignoring' % (recipe_data.getVar('FILE', True), ct))
        return

    summary = recipe_data.getVar('SUMMARY', True) or recipe_data.getVar('DESCRIPTION', True)
    recipesymbol = RecipeSymbol.symbol(recipe_data.getVar('PN', True), layerbranch, summary=summary)

    try:
        latest_upgrade = RecipeUpgrade.objects.filter(
                recipesymbol=recipesymbol).order_by('-commit_date')[0]
        prev_pv = latest_upgrade.version
    except KeyboardInterrupt:
        raise
    except:
        prev_pv = None

    if prev_pv is None:
        logger.debug("%s: Initial upgrade ( -> %s)." % (pn, pv))
        _save_upgrade(recipesymbol, layerbranch, pv, ct, title, info, filepath, logger)
    else:
        from common import get_recipe_pv_without_srcpv

        (ppv, _, _) = get_recipe_pv_without_srcpv(prev_pv,
                get_pv_type(prev_pv))
        (npv, _, _) = get_recipe_pv_without_srcpv(pv,
                get_pv_type(pv))

        try:
            if npv == 'git':
                logger.debug("%s: Avoiding upgrade to unversioned git." % pn)
            elif ppv == 'git' or vercmp_string(ppv, npv) == -1:
                if initial is True:
                    logger.debug("%s: Update initial upgrade ( -> %s)." % \
                            (pn, pv)) 
                    latest_upgrade.filepath = filepath
                    latest_upgrade.version = pv
                    latest_upgrade.save()
                else:
                    logger.debug("%s: detected upgrade (%s -> %s)" \
                            " in ct %s." % (pn, prev_pv, pv, ct))
                    _save_upgrade(recipesymbol, layerbranch, pv, ct, title, info, filepath, logger)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error("%s: fail to detect upgrade (%s -> %s)" \
                            " in ct %s: %s" % (pn, prev_pv, pv, ct, str(e)))


"""
    Returns a list containing the fullpaths to the recipes from a commit.
"""
def _get_recipes_filenames(ct, repo, repodir, layersubdir_start, logger):
    import glob
    ct_files = []
    deleted = []
    moved_files = []

    incdirs = []
    commitobj = repo.commit(ct)
    for parent in commitobj.parents:
        diff = parent.diff(commitobj)
        for diffitem in diff:
            if layersubdir_start and not (diffitem.a_path.startswith(layersubdir_start) or diffitem.b_path.startswith(layersubdir_start)):
                # Not in this layer, skip it
                continue

            (typename, _, _) = recipeparse.detect_file_type(diffitem.a_path,
                                        layersubdir_start)

            if not diffitem.b_path or diffitem.deleted_file or not diffitem.b_path.startswith(layersubdir_start):
                # Deleted, or moved out of the layer (which we treat as a delete)
                if typename == 'recipe':
                    deleted.append(diffitem.a_path)
                continue

            if typename == 'recipe':
                ct_files.append(os.path.join(repodir, diffitem.b_path))
                if diffitem.a_path != diffitem.b_path:
                    moved_files.append((diffitem.a_path, diffitem.b_path))
            elif typename == 'incfile':
                fpath = os.path.dirname(os.path.join(repodir, diffitem.a_path))
                if not fpath in incdirs:
                    incdirs.append(fpath)

    for fpath in incdirs:
        # Let's just assume that all .bb files next to a .inc need to be checked
        for f in glob.glob(os.path.join(fpath, '*.bb')):
            if not f in ct_files:
                ct_files.append(f)

    return ct_files, deleted, moved_files


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
    from rrs.models import Release, RecipeUpgrade
    layerbranch = LayerBranch.objects.get(id=layerbranch_id)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    layer = layerbranch.layer
    urldir = str(layer.get_fetch_dir())
    repodir = os.path.join(fetchdir, urldir)
    layerdir = os.path.join(repodir, str(layerbranch.vcs_subdir))

    if layerbranch.vcs_subdir:
        layersubdir_start = layerbranch.vcs_subdir
        if not layersubdir_start.endswith('/'):
            layersubdir_start += '/'
    else:
        layersubdir_start = ''

    repo = git.Repo(repodir)
    if repo.bare:
        logger.error('Repository %s is bare, not supported' % repodir)
        sys.exit(1)

    commitdate = checkout_layer_deps(layerbranch, commit, fetchdir, logger)

    if options.initial:
        fns = None
        deleted = []
        moved = []
    else:
        fns, deleted, moved = _get_recipes_filenames(commit, repo, repodir, layersubdir_start, logger)
        if not (fns or deleted or moved):
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

        fn_data = {}
        for recipe_data in recipes:
            fn = os.path.relpath(recipe_data.getVar('FILE', True), repodir)
            fn_data[fn] = recipe_data

        seen_pns = []
        try:
            with transaction.atomic():
                for a, b in moved:
                    logger.debug('Move %s -> %s' % (a,b))
                    rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=a).order_by('-commit_date')
                    recipe_data = fn_data.get(b, None)
                    if recipe_data:
                        pn = recipe_data.getVar('PN', True)
                        ru = rus.first()
                        if ru and ru.recipesymbol.pn != pn:
                            # PN has been changed! We need to mark the old record as deleted
                            logger.debug('PN changed: %s -> %s' % (ru.recipesymbol.pn, pn))
                            if a not in deleted:
                                deleted.append(a)
                    else:
                        logger.warning('Unable to find parsed data for recipe %s' % b)

                    if a not in deleted:
                        # Need to keep filepath up-to-date, otherwise we won't be able to
                        # find the record if we need to mark it as deleted later
                        for ru in rus:
                            ru.filepath = b
                            ru.save()

                for recipe_data in recipes:
                    filepath = os.path.relpath(recipe_data.getVar('FILE', True), repodir)
                    _create_upgrade(recipe_data, layerbranch, recordcommit, title,
                            info, filepath, logger, initial=options.initial)
                    seen_pns.append(recipe_data.getVar('PN', True))

                for df in deleted:
                    rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=df).order_by('-commit_date')
                    for ru in rus:
                        other_rus = RecipeUpgrade.objects.filter(recipesymbol=ru.recipesymbol, commit_date__gt=ru.commit_date).exclude(filepath=df).order_by('-commit_date')
                        # We make a distinction between deleting just one version and the entire recipe being deleted
                        upgrade_type = 'R'
                        for other_ru in other_rus:
                            if other_ru.upgrade_type == 'R':
                                logger.debug('There is a delete: %s' % other_ru)
                                upgrade_type = ''
                                break
                            if os.path.exists(os.path.join(repodir, other_ru.filepath)):
                                upgrade_type = 'N'
                        if not upgrade_type:
                            continue
                        if ru.upgrade_type != upgrade_type and ru.recipesymbol.pn not in seen_pns:
                            logger.debug("%s: marking as deleted (%s)" % (ru.recipesymbol.pn, ru.filepath))
                            _save_upgrade(ru.recipesymbol, layerbranch, ru.version, recordcommit, title, info, df, logger, upgrade_type=upgrade_type)
                            break

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

