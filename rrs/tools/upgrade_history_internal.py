# Internal script called by rrs_upgrade_history.py
#
# To detect package versions of the recipes the script uses the name of the recipe.
#
# Copyright (C) 2015, 2018 Intel Corporation
# Authors: Anibal Limon <anibal.limon@linux.intel.com>
#          Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT


import sys
import os
import optparse
import logging
import re
from pkg_resources import parse_version
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


oecore_bad_revs = {
    '40a904bf8bc1279c3da0893c003f740f1d2066c2': [
        '2dfbff215f3567252fdfbd5704e6740a30ad41b4',
        '543e39ad5e2baa0f1ece013a89483783e6b15dd9',
        'a39830b77f567e2361f1ced49bfdce52591e220c',
        'c88304a78e528596ca481cabe273749c286c352a',
        '21d015f6c9927598d64c48c925638619b25cf232',
        'da29440633706fb7a346391d97894d6f2cbb0d01',
        'b9b254da08c1db94ac9ded5f67d7e2e82e3b9be7',
        '12e859dfb70f8aae40edfd88b143b6c771f4e1a6',
        'ec957a03010949a93fbebd3e7b8b924ebc055ef7',
        '2f0dd67a5a8d4269f5155004d532d8fa972b3223',
        '1c2197f96d69547e10b74dc722d9a569d9a2b2b6',
        '7aa94abac09be6beb7ce14a2b9a409e934465706',
        '1a0ee6b0f194807b9eac1207c43ba3fae4d1f94c',
        'bbd9524256461f1bcafd4103edd575e668de76f8',
        '68e0080a924654245f04cf92c2579abd9e5bc658',
        '1ed072515f2a23de75ee56b86d8607c85b42605c',
        'cb3c0343becc8bb2ebf4e9c12782c509a3d7754d',
        '94793d08b0087b7f579b2ca5adae3343864e5f66',
        '802c4029f90cee3027b6bc62c5201e8b29f02557',
        'b992be195821e110691434e4a743b753bc04b3c4',
        '6414d23cd23fc6ed2d31a7b55fce1be82a09ae67',
        '458c835fe05279467ab781aab811498ab80f6904',
        '31c9b42aaeef3ad66e05e51b8209e87f2a22f091',
        'c70b70f045a5ccf62b19060f3438b38d9914e9a2',
        'af4f0d44acef328245dfe1bd102bb5e61293ee2d',
        '747c7dc8702d2241475894876d06a2f1f2b29fed',
        '369bbf393438ae4a76ab0d1817463c6f735816ea',
        'dd5208ae22d47504443785daece4bff6331d8904',
        'c9fdf3d046606a0becb2e6b566a481c483b9021a',
        '13269dfbbc62faef32595343dc78250fdb2a2946',
        '270a1e9bcf26a43f5cbdc5b901c4c6f79495311d',
        '15e876ada73fe8e98284d14dec166007b5767f19',
        '647db1d9eb65b225ffbb6953f796232026bfa935',
        '75529d384bfeaf52befccb892cf41f22dc02668b',
        'ec9fcdf14d3e2aefc5af1e53a69f056db6ea83f5',
        '84980150ff4a2c27acd1f27123f200e03bee8c4b',
        'c93dc7dd18a752d9523e11c6c4dce1908b5970b4',
        '2d9a8a5539342faa1827f4902b1095a9f3448c66',
        'b2cd021887e12d9f5b8ba48d9be3c2f2119c8e2a',
        'da3659155cd1825a4a8d3d7c5288b4273714de15',
        '4af90876914e5f2ccc5b7f833cd43c239c2dac55',
        '8a771f22980f766b71f3ea0825568fc5c669e444',
        'b0338efcdabeec79c568c74b6888d7d523e8e9dc',
        'f3f394913b4e4a7c601ad1158faaf8b9d493e1c7',
        'b3e246fef166030f327b5a852718ea907ada1759',
        'a8a2c5ec891286a1e7fd5ebdd33565f9ae3965c2',
        'ee48cb68e5d91ba108cccdabce003233290ba816',
        '088814ef79015d9df0c8c8bc61219507cfe52ad5',
        'c03cef42e079e4ed3d1e4f401722778157158bd6',
        'bcdaa93dc70411da8876364ae67d0bf2456a3611',
        'e8dfe9799e473e0ba911a0670aa23e8e8d700223',
        'e38e56e28f2090e2b8013546f4dd76da8d59f766',
        '85981cbbf0ce48a6d82bc39248afa9540ca858d8',
        '147f5a665fe5073027d92e4acac631f15f08f79f',
        'b503b1fe9a71f70726c92f46a71fc49615256fce',
        '4972faf1bf20f07a1c1f608bc421c6fd05651594',
        '309a02931779f32d1139cc1169a039cbe4638706',
    ],
    'fcd6b38bab8517d83e1ed48eef1bca9a9a190f57': [
        'dad9617809c60ec5f11d4780b0afa1cffa1efed5',
        '0a064f2216895db0181ee033a785328e704ddc0b',
        'de6e98f272e623ce72e724e66920eecf10cb2d41',
        '30d02e2aa2d42fdf76271234b2dc9f37bc46b250',
        'e8cfab060f4ff3c4c16387871354d407910e87aa',
        '25d4d8274bac696a484f83d7f3ada778cf95f4d0',
        '210e290c9251839dc74e3aabdcea3655dd707a50',
        '23c27d9d936efaa17da00525f1d2e2f98c53abc7',
        'ea6245d2383e2ba905ef9f1ba210e5dadc779ad8',
        'ecfcc5dad20943b762a741546732a6c447265251',
        'd022b4335100612d6596cc4c4956cb98ed5873cc',
        'caebd862bac7eed725e0f0321bf50793671b5312',
        '2476bdcbef591e951d11d57d53f1315848758571',
        'bb4685af1bffe17b3aa92a6d21398f38a44ea874',
        '737a095fcde773a36e0fee1f27b74aaa88062386',
        '3dd26cd6b3d731f7698f6fbcd1947969f360cdc4',
    ],
}
oecore_bad_revs_2 = [
    '2dfbff215f3567252fdfbd5704e6740a30ad41b4',
    '543e39ad5e2baa0f1ece013a89483783e6b15dd9',
    'a39830b77f567e2361f1ced49bfdce52591e220c',
    'c88304a78e528596ca481cabe273749c286c352a',
    '21d015f6c9927598d64c48c925638619b25cf232',
    'da29440633706fb7a346391d97894d6f2cbb0d01',
    'b9b254da08c1db94ac9ded5f67d7e2e82e3b9be7',
    '12e859dfb70f8aae40edfd88b143b6c771f4e1a6',
    'ec957a03010949a93fbebd3e7b8b924ebc055ef7',
    '2f0dd67a5a8d4269f5155004d532d8fa972b3223',
    '1c2197f96d69547e10b74dc722d9a569d9a2b2b6',
    '7aa94abac09be6beb7ce14a2b9a409e934465706',
    '1a0ee6b0f194807b9eac1207c43ba3fae4d1f94c',
    'bbd9524256461f1bcafd4103edd575e668de76f8',
    '68e0080a924654245f04cf92c2579abd9e5bc658',
    '1ed072515f2a23de75ee56b86d8607c85b42605c',
    'cb3c0343becc8bb2ebf4e9c12782c509a3d7754d',
    '94793d08b0087b7f579b2ca5adae3343864e5f66',
    '802c4029f90cee3027b6bc62c5201e8b29f02557',
    'b992be195821e110691434e4a743b753bc04b3c4',
    '6414d23cd23fc6ed2d31a7b55fce1be82a09ae67',
    '458c835fe05279467ab781aab811498ab80f6904',
    '31c9b42aaeef3ad66e05e51b8209e87f2a22f091',
    'c70b70f045a5ccf62b19060f3438b38d9914e9a2',
    'af4f0d44acef328245dfe1bd102bb5e61293ee2d',
    '747c7dc8702d2241475894876d06a2f1f2b29fed',
    '369bbf393438ae4a76ab0d1817463c6f735816ea',
    'dd5208ae22d47504443785daece4bff6331d8904',
    'c9fdf3d046606a0becb2e6b566a481c483b9021a',
    '13269dfbbc62faef32595343dc78250fdb2a2946',
    '270a1e9bcf26a43f5cbdc5b901c4c6f79495311d',
    '15e876ada73fe8e98284d14dec166007b5767f19',
    '647db1d9eb65b225ffbb6953f796232026bfa935',
    '75529d384bfeaf52befccb892cf41f22dc02668b',
    'ec9fcdf14d3e2aefc5af1e53a69f056db6ea83f5',
    '84980150ff4a2c27acd1f27123f200e03bee8c4b',
    'c93dc7dd18a752d9523e11c6c4dce1908b5970b4',
    '2d9a8a5539342faa1827f4902b1095a9f3448c66',
    'b2cd021887e12d9f5b8ba48d9be3c2f2119c8e2a',
    'da3659155cd1825a4a8d3d7c5288b4273714de15',
    '4af90876914e5f2ccc5b7f833cd43c239c2dac55',
    '8a771f22980f766b71f3ea0825568fc5c669e444',
    'b0338efcdabeec79c568c74b6888d7d523e8e9dc',
    'f3f394913b4e4a7c601ad1158faaf8b9d493e1c7',
    'b3e246fef166030f327b5a852718ea907ada1759',
    'a8a2c5ec891286a1e7fd5ebdd33565f9ae3965c2',
    'ee48cb68e5d91ba108cccdabce003233290ba816',
    '088814ef79015d9df0c8c8bc61219507cfe52ad5',
    'c03cef42e079e4ed3d1e4f401722778157158bd6',
    'bcdaa93dc70411da8876364ae67d0bf2456a3611',
    'e8dfe9799e473e0ba911a0670aa23e8e8d700223',
    'e38e56e28f2090e2b8013546f4dd76da8d59f766',
    '85981cbbf0ce48a6d82bc39248afa9540ca858d8',
    '147f5a665fe5073027d92e4acac631f15f08f79f',
    'b503b1fe9a71f70726c92f46a71fc49615256fce',
    '4972faf1bf20f07a1c1f608bc421c6fd05651594',
    '309a02931779f32d1139cc1169a039cbe4638706',
]


"""
    Store upgrade into RecipeUpgrade model.
"""
def _save_upgrade(recipesymbol, layerbranch, pv, srcrev, license, commit, title, info, filepath, logger, upgrade_type=None, orig_filepath=None, prev_version=None):
    from rrs.models import Maintainer, RecipeUpgrade

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
    upgrade.srcrev = srcrev
    upgrade.sha1 = commit
    upgrade.title = title.strip()
    upgrade.filepath = filepath
    if upgrade_type:
        upgrade.upgrade_type = upgrade_type
    if orig_filepath:
        upgrade.orig_filepath = orig_filepath
    if prev_version:
        upgrade.prev_version = prev_version
    upgrade.license = license
    upgrade.regroup()
    upgrade.save()

"""
    Create upgrade receives new recipe_data and cmp versions.
"""
def _create_upgrade(recipe_data, layerbranch, ct, title, info, filepath, logger, initial=False, orig_filepath=None):
    from rrs.models import RecipeUpgrade, RecipeSymbol, RecipeUpgradeGroupRule
    from bb.utils import vercmp_string

    pn = recipe_data.getVar('PN', True)
    pv = recipe_data.getVar('PV', True)
    srcrev = recipe_data.getVar('SRCREV', True)
    if srcrev == 'INVALID':
        srcrev = ''
    license = recipe_data.getVar('LICENSE', True)

    if '..' in pv or pv.endswith('.'):
        logger.warn('Invalid version for recipe %s in commit %s, ignoring' % (recipe_data.getVar('FILE', True), ct))
        return

    summary = recipe_data.getVar('SUMMARY', True) or recipe_data.getVar('DESCRIPTION', True)
    recipesymbol = RecipeSymbol.symbol(recipe_data.getVar('PN', True), layerbranch, summary=summary)

    all_rupgrades = RecipeUpgrade.objects.filter(recipesymbol=recipesymbol).exclude(sha1=ct)
    rupgrades = all_rupgrades
    group = RecipeUpgradeGroupRule.group_for_params(recipesymbol, pv, license)
    if group:
        rupgrades = all_rupgrades.filter(group=group)
    latest_upgrade = rupgrades.order_by('-commit_date', '-id').first()
    if latest_upgrade:
        prev_pv = latest_upgrade.version
        prev_srcrev = latest_upgrade.srcrev
    else:
        prev_pv = None
        prev_srcrev = ''

    if prev_pv is None:
        logger.debug("%s: Initial upgrade ( -> %s)." % (pn, pv))
        _save_upgrade(recipesymbol, layerbranch, pv, srcrev, license, ct, title, info, filepath, logger)
    else:
        from common import get_recipe_pv_without_srcpv

        (ppv, _, _) = get_recipe_pv_without_srcpv(prev_pv,
                get_pv_type(prev_pv))
        (npv, _, _) = get_recipe_pv_without_srcpv(pv,
                get_pv_type(pv))

        try:
            vercmp_result = 0
            if not (npv == 'git' or ppv == 'git'):
                vercmp_result = vercmp_string(ppv, npv)

            if npv == 'git':
                logger.debug("%s: Avoiding upgrade to unversioned git." % pn)
            elif ppv == 'git' or vercmp_result != 0 or srcrev != prev_srcrev or latest_upgrade.upgrade_type == 'R':
                if initial is True:
                    logger.debug("%s: Update initial upgrade ( -> %s)." % \
                            (pn, pv)) 
                    latest_upgrade.filepath = filepath
                    latest_upgrade.version = pv
                    latest_upgrade.save()
                else:
                    # Check if the "new" version is already in the database
                    same_pv_upgrade = all_rupgrades.filter(version=pv).order_by('-commit_date', '-id').first()
                    if same_pv_upgrade and \
                            not all_rupgrades.filter(prev_version=pv, commit_date__gt=same_pv_upgrade.commit_date).exists() \
                            and \
                            not all_rupgrades.filter(upgrade_type__in=['R', 'N'], commit_date__gt=same_pv_upgrade.commit_date).exists():
                        # The "previous" recipe is still present, we won't call this an upgrade
                        logger.debug('%s: new version %s already exists' % (pn, pv))
                        return
                    upgrade_type = 'U'
                    if vercmp_result == 1:
                        upgrade_type = 'D'
                    op = {'U': 'upgrade', 'D': 'downgrade'}[upgrade_type]
                    logger.debug("%s: detected %s (%s -> %s)" \
                            " in ct %s." % (pn, op, prev_pv, pv, ct))
                    _save_upgrade(recipesymbol, layerbranch, pv, srcrev, license, ct, title, info, filepath, logger, upgrade_type=upgrade_type, orig_filepath=orig_filepath, prev_version=prev_pv)
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
    added_files = []

    incdirs = []
    commitobj = repo.commit(ct)
    for parent in commitobj.parents:
        diff = parent.diff(commitobj)
        for diffitem in diff:
            if layersubdir_start and not (diffitem.a_path.startswith(layersubdir_start) or diffitem.b_path.startswith(layersubdir_start)):
                # Not in this layer, skip it
                continue
            if diffitem.a_path.startswith(layersubdir_start + 'lib/') or diffitem.b_path.startswith(layersubdir_start + 'lib/'):
                # A little bit hacky, but we pick up templates otherwise
                continue

            (typename, _, _) = recipeparse.detect_file_type(diffitem.a_path,
                                        layersubdir_start)

            if not diffitem.b_path or diffitem.deleted_file or not diffitem.b_path.startswith(layersubdir_start):
                # Deleted, or moved out of the layer (which we treat as a delete)
                if typename == 'recipe':
                    deleted.append(diffitem.a_path)
                continue

            if typename == 'recipe':
                (to_typename, _, _) = recipeparse.detect_file_type(diffitem.b_path,
                                            layersubdir_start)
                if to_typename == 'recipe':
                    ct_files.append(os.path.join(repodir, diffitem.b_path))
                    if diffitem.a_path is None or diffitem.new_file:
                        added_files.append(diffitem.b_path)
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

    # Check moves for recipe -> inc with an added recipe
    # (i.e. the move should really be to the newly added recipe)
    # example: d5a95dc8985a42bb7e50bc4e7dc6b012d711ff08 in OE-Core
    for i,(a,b) in enumerate(moved_files):
        if b.endswith('.inc'):
            for af in added_files:
                # This is naive, but good enough
                if af.rsplit('_')[0] == a.rsplit('_')[0]:
                    moved_files[i] = (a,af)

    return ct_files, deleted, moved_files


def checkout_layer_deps(layerbranch, commit, fetchdir, logger):
    """ Check out the repositories for a layer and its dependencies """

    oecore_map = {}
    if layerbranch.layer.name != 'openembedded-core':
        # Filter out some bad commits for OE-Core
        for good_rev, bad_revs in oecore_bad_revs.items():
            for bad_rev in bad_revs:
                oecore_map[bad_rev] = good_rev

    # Some layers will be in the same repository, so we only want to check those out once
    done_repos = []
    def checkout_layer(lb, lcommit=None, lcommitdate=None, force=False):
        urldir = str(lb.layer.get_fetch_dir())
        repodir = os.path.join(fetchdir, urldir)
        if not repodir in done_repos:
            if not lcommit:
                lcommit = utils.runcmd(['git', 'rev-list', '-1', '--before=%s' % lcommitdate, 'origin/master'], repodir, logger=logger).strip()
            if lb.layer.name == 'openembedded-core':
                lmapcommit = oecore_map.get(lcommit, None)
                if lmapcommit:
                    logger.debug('Preferring OE-Core revision %s over %s' % (lmapcommit, lcommit))
                    lcommit = lmapcommit
            utils.checkout_repo(repodir, lcommit, logger, force)
            if lcommit in oecore_bad_revs_2:
                # Fix issue that was introduced in 309a02931779f32d1139cc1169a039cbe4638706 and fixed in 40a904bf8bc1279c3da0893c003f740f1d2066c2
                with open(os.path.join(repodir, 'meta/conf/bitbake.conf'), 'r') as f:
                    lines = f.readlines()
                lines.insert(0, 'BBINCLUDED ?= ""\n')
                with open(os.path.join(repodir, 'meta/conf/bitbake.conf'), 'w') as f:
                    f.writelines(lines)
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
        if options.filter_files:
            filepath_start = options.filter_files
        else:
            filepath_start = layersubdir_start
        fns, deleted, moved = _get_recipes_filenames(commit, repo, repodir, filepath_start, logger)
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
                # Handle recipes where PN has changed
                for a, b in moved:
                    logger.debug('Move %s -> %s' % (a,b))
                    rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=a).order_by('-commit_date', '-id')
                    recipe_data = fn_data.get(b, None)
                    if recipe_data:
                        pn = recipe_data.getVar('PN', True)
                        ru = rus.first()
                        if ru and ru.recipesymbol.pn != pn:
                            # PN has been changed! We need to mark the old record as deleted
                            logger.debug('PN changed (with move): %s -> %s' % (ru.recipesymbol.pn, pn))
                            if a not in deleted:
                                deleted.append(a)
                    else:
                        logger.warning('Unable to find parsed data for recipe %s' % b)

                # Handle recipes that exist at this point in time (which may have upgraded)
                for recipe_data in recipes:
                    pn = recipe_data.getVar('PN', True)
                    filepath = os.path.relpath(recipe_data.getVar('FILE', True), repodir)
                    # Check if PN has changed internally
                    rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=filepath).order_by('-commit_date', '-id')
                    deleted_pns = rus.filter(upgrade_type__in=['R', 'N']).values_list('recipesymbol__pn', flat=True).distinct()
                    for ru in rus:
                        if ru.recipesymbol.pn != pn and ru.recipesymbol.pn not in deleted_pns and ru.upgrade_type not in ['R', 'N']:
                            # PN changed (set within recipe), we need to mark the old recipe as deleted
                            logger.debug('PN changed (without move): %s -> %s' % (ru.recipesymbol.pn, pn))
                            _save_upgrade(ru.recipesymbol, layerbranch, ru.version, ru.srcrev, ru.license, recordcommit, title, info, ru.filepath, logger, upgrade_type='R')
                    orig_filepath = None
                    for a, b in moved:
                        if b == filepath:
                            orig_filepath = a
                            break
                    _create_upgrade(recipe_data, layerbranch, recordcommit, title,
                            info, filepath, logger, initial=options.initial, orig_filepath=orig_filepath)
                    seen_pns.append(pn)

                # Handle recipes that have been moved without it being an upgrade/delete
                for a, b in moved:
                    if a not in deleted:
                        rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=a).order_by('-commit_date', '-id')
                        if rus:
                            ru = rus.first()
                            if not RecipeUpgrade.objects.filter(recipesymbol=ru.recipesymbol, filepath=b).exists():
                                # Need to record the move, otherwise we won't be able to
                                # find the record if we need to mark the recipe as deleted later
                                _save_upgrade(ru.recipesymbol, layerbranch, ru.version, ru.srcrev, ru.license, recordcommit, title, info, b, logger, upgrade_type='M', orig_filepath=a)

                # Handle deleted recipes
                for df in deleted:
                    rus = RecipeUpgrade.objects.filter(recipesymbol__layerbranch=layerbranch, filepath=df).order_by('-commit_date', '-id')
                    for ru in rus:
                        other_rus = RecipeUpgrade.objects.filter(recipesymbol=ru.recipesymbol, commit_date__gte=ru.commit_date).exclude(filepath=df).order_by('-commit_date', '-id')
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
                            if upgrade_type == 'R':
                                finalmsg = ' [FINAL]'
                            else:
                                finalmsg = ''
                            logger.debug("%s: marking as deleted%s (%s)" % (ru.recipesymbol.pn, finalmsg, ru.filepath))
                            _save_upgrade(ru.recipesymbol, layerbranch, ru.version, ru.srcrev, ru.license, recordcommit, title, info, df, logger, upgrade_type=upgrade_type)
                            break

                if options.dry_run:
                    raise DryRunRollbackException
        except DryRunRollbackException:
            pass

    finally:
        if tinfoil and hasattr(tinfoil, 'shutdown') and (parse_version(bb.__version__) > parse_version("1.27")):
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

        parser.add_option("-F", "--filter-files",
                help="Only operate on a specified subset of files (wildcards allowed)",
                action="store", dest="filter_files", default='')

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

