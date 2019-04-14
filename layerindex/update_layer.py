#!/usr/bin/env python

# Update layer index database for a single layer
#
# Copyright (C) 2013-2016 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import optparse
import logging
from datetime import datetime
import re
import tempfile
import shutil
import errno
from distutils.version import LooseVersion
import itertools
import utils
import recipeparse
import layerconfparse

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = utils.logger_create('LayerIndexUpdate')

# Ensure PythonGit is installed (buildhistory_analysis needs it)
try:
    import git
except ImportError:
    logger.error("Please install PythonGit 0.3.1 or later in order to use this script")
    sys.exit(1)


class DryRunRollbackException(Exception):
    pass


def check_machine_conf(path, subdir_start):
    subpath = path[len(subdir_start):]
    res = conf_re.match(subpath)
    if res:
        return res.group(1)
    return None

def split_recipe_fn(path):
    splitfn = os.path.basename(path).split('.bb')[0].split('_', 2)
    pn = splitfn[0]
    if len(splitfn) > 1:
        pv = splitfn[1]
    else:
        pv = "1.0"
    return (pn, pv)

def collect_patch(recipe, patchfn, index, layerdir_start, stop_on_error):
    from django.db import DatabaseError
    from layerindex.models import Patch

    patchrec = Patch()
    patchrec.recipe = recipe
    patchrec.path = os.path.relpath(patchfn, layerdir_start)
    patchrec.src_path = os.path.relpath(patchrec.path, recipe.filepath)
    patchrec.apply_order = index
    try:
        patchrec.read_status_from_file(patchfn, logger)
        patchrec.save()
    except DatabaseError:
        raise
    except Exception as e:
        if stop_on_error:
            raise
        else:
            logger.error("Unable to read patch %s: %s", patchfn, str(e))
            patchrec.save()

def collect_patches(recipe, envdata, layerdir_start, stop_on_error):
    from layerindex.models import Patch

    try:
        import oe.recipeutils
    except ImportError:
        logger.warn('Failed to find lib/oe/recipeutils.py in layers - patches will not be imported')
        return

    Patch.objects.filter(recipe=recipe).delete()
    patches = oe.recipeutils.get_recipe_patches(envdata)
    for i, patch in enumerate(patches):
        if not patch.startswith(layerdir_start):
            # Likely a remote patch, skip it
            continue
        collect_patch(recipe, patch, i, layerdir_start, stop_on_error)

def update_recipe_file(tinfoil, data, path, recipe, layerdir_start, repodir, stop_on_error, skip_patches=False):
    from django.db import DatabaseError

    fn = str(os.path.join(path, recipe.filename))
    from layerindex.models import PackageConfig, StaticBuildDep, DynamicBuildDep, Source, Patch
    try:
        logger.debug('Updating recipe %s' % fn)
        if hasattr(tinfoil, 'parse_recipe_file'):
            envdata = tinfoil.parse_recipe_file(fn, appends=False, config_data=data)
        else:
            envdata = bb.cache.Cache.loadDataFull(fn, [], data)
        envdata.setVar('SRCPV', 'X')
        recipe.pn = envdata.getVar("PN", True)
        recipe.pv = envdata.getVar("PV", True)
        recipe.summary = envdata.getVar("SUMMARY", True)
        recipe.description = envdata.getVar("DESCRIPTION", True)
        recipe.section = envdata.getVar("SECTION", True)
        recipe.license = envdata.getVar("LICENSE", True)
        recipe.homepage = envdata.getVar("HOMEPAGE", True)
        recipe.bugtracker = envdata.getVar("BUGTRACKER", True) or ""
        recipe.provides = envdata.getVar("PROVIDES", True) or ""
        recipe.bbclassextend = envdata.getVar("BBCLASSEXTEND", True) or ""
        # Handle recipe inherits for this recipe
        gr = set(data.getVar("__inherit_cache", True) or [])
        lr = set(envdata.getVar("__inherit_cache", True) or [])
        recipe.inherits = ' '.join(sorted({os.path.splitext(os.path.basename(r))[0] for r in lr if r not in gr}))
        recipe.blacklisted = envdata.getVarFlag('PNBLACKLIST', recipe.pn, True) or ""
        for confvar in ['EXTRA_OEMESON', 'EXTRA_OECMAKE', 'EXTRA_OESCONS', 'EXTRA_OECONF']:
            recipe.configopts = envdata.getVar(confvar, True) or ""
            if recipe.configopts:
                break
        else:
            recipe.configopts = ''
        recipe.save()

        # Handle sources
        old_urls = list(recipe.source_set.values_list('url', flat=True))
        for url in (envdata.getVar('SRC_URI', True) or '').split():
            if not url.startswith('file://'):
                url = url.split(';')[0]
                if url in old_urls:
                    old_urls.remove(url)
                else:
                    src = Source(recipe=recipe, url=url)
                    src.save()
        for url in old_urls:
            recipe.source_set.filter(url=url).delete()

        recipeparse.handle_recipe_depends(recipe, envdata.getVar('DEPENDS', True) or '', envdata.getVarFlags('PACKAGECONFIG'))

        if not skip_patches:
            # Handle patches
            collect_patches(recipe, envdata, layerdir_start, stop_on_error)

        # Get file dependencies within this layer
        deps = envdata.getVar('__depends', True)
        filedeps = []
        for depstr, date in deps:
            found = False
            if depstr.startswith(layerdir_start) and not depstr.endswith('/conf/layer.conf'):
                filedeps.append(os.path.relpath(depstr, repodir))
        from layerindex.models import RecipeFileDependency

        recipedeps_delete = []

        recipedeps = RecipeFileDependency.objects.filter(recipe=recipe)

        for values in recipedeps.values('path'):
            if 'path' in values:
                recipedeps_delete.append(values['path'])

        for filedep in filedeps:
            if filedep in recipedeps_delete:
                recipedeps_delete.remove(filedep)
                continue
            # New item, add it...
            recipedep = RecipeFileDependency()
            recipedep.layerbranch = recipe.layerbranch
            recipedep.recipe = recipe
            recipedep.path = filedep
            recipedep.save()

        for filedep in recipedeps_delete:
            recipedeps.filter(path=filedep).delete()

    except KeyboardInterrupt:
        raise
    except DatabaseError:
        raise
    except BaseException as e:
        if stop_on_error:
            raise
        else:
            if not recipe.pn:
                recipe.pn = recipe.filename[:-3].split('_')[0]
            logger.error("Unable to read %s: %s", fn, str(e))

def update_machine_conf_file(path, machine):
    logger.debug('Updating machine %s' % path)
    desc = ""
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#@NAME:'):
                desc = line[7:].strip()
            if line.startswith('#@DESCRIPTION:'):
                desc = line[14:].strip()
                desc = re.sub(r'Machine configuration for( running)*( an)*( the)*', '', desc)
                break
    machine.description = desc

def update_distro_conf_file(path, distro, d):
    logger.debug('Updating distro %s' % path)
    desc = ""
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#@NAME:'):
                desc = line[7:].strip()
            if line.startswith('#@DESCRIPTION:'):
                desc = line[14:].strip()
                desc = re.sub(r'Distribution configuration for( running)*( an)*( the)*', '', desc)
                break

    distro_name = ''
    try:
        d = utils.parse_conf(path, d)
        distro_name = d.getVar('DISTRO_NAME', True)
    except Exception as e:
        logger.warn('Error parsing distro configuration file %s: %s' % (path, str(e)))

    if distro_name:
        distro.description = distro_name
    else:
        distro.description = desc

def main():
    if LooseVersion(git.__version__) < '0.3.1':
        logger.error("Version of GitPython is too old, please install GitPython (python-git) 0.3.1 or later in order to use this script")
        sys.exit(1)


    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-b", "--branch",
            help = "Specify branch to update",
            action="store", dest="branch", default='master')
    parser.add_option("-l", "--layer",
            help = "Layer to update",
            action="store", dest="layer")
    parser.add_option("-r", "--reload",
            help = "Reload recipe data instead of updating since last update",
            action="store_true", dest="reload")
    parser.add_option("", "--fullreload",
            help = "Discard existing recipe data and fetch it from scratch",
            action="store_true", dest="fullreload")
    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("", "--nocheckout",
            help = "Don't check out branches",
            action="store_true", dest="nocheckout")
    parser.add_option("", "--stop-on-error",
            help = "Stop on first parsing error",
            action="store_true", default=False, dest="stop_on_error")
    parser.add_option("-i", "--initial",
            help = "Print initial values parsed from layer.conf only",
            action="store_true")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")
    parser.add_option("", "--keep-temp",
            help = "Preserve temporary directory at the end instead of deleting it",
            action="store_true")

    options, args = parser.parse_args(sys.argv)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)

    if options.fullreload:
        options.reload = True

    utils.setup_django()
    import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, RecipeFileDependency, Machine, Distro, BBAppend, BBClass, IncFile
    from django.db import transaction

    logger.setLevel(options.loglevel)

    branch = utils.get_branch(options.branch)
    if not branch:
        logger.error("Specified branch %s is not valid" % options.branch)
        sys.exit(1)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    bitbakepath = os.path.join(fetchdir, 'bitbake')

    layer = utils.get_layer(options.layer)
    urldir = layer.get_fetch_dir()
    repodir = os.path.join(fetchdir, urldir)

    layerbranch = layer.get_layerbranch(options.branch)

    branchname = options.branch
    branchdesc = options.branch
    if layerbranch:
        if layerbranch.actual_branch:
            branchname = layerbranch.actual_branch
            branchdesc = "%s (%s)" % (options.branch, branchname)

    # Collect repo info
    repo = git.Repo(repodir)
    if repo.bare:
        logger.error('Repository %s is bare, not supported' % repodir)
        sys.exit(1)
    topcommit = repo.commit('origin/%s' % branchname)
    if options.nocheckout:
        topcommit = repo.commit('HEAD')

    tinfoil = None
    tempdir = None
    try:
        with transaction.atomic():
            newbranch = False
            if not layerbranch:
                # LayerBranch doesn't exist for this branch, create it
                newbranch = True
                layerbranch = LayerBranch()
                layerbranch.layer = layer
                layerbranch.branch = branch
                layerbranch_source = layer.get_layerbranch(branch)
                if not layerbranch_source:
                    layerbranch_source = layer.get_layerbranch(None)
                if layerbranch_source:
                    layerbranch.vcs_subdir = layerbranch_source.vcs_subdir
                layerbranch.save()
                if layerbranch_source:
                    for maintainer in layerbranch_source.layermaintainer_set.all():
                        maintainer.pk = None
                        maintainer.id = None
                        maintainer.layerbranch = layerbranch
                        maintainer.save()

            if layerbranch.vcs_subdir and not options.nocheckout:
                # Find latest commit in subdirectory
                # A bit odd to do it this way but apparently there's no other way in the GitPython API
                topcommit = next(repo.iter_commits('origin/%s' % branchname, paths=layerbranch.vcs_subdir), None)

            layerdir = os.path.join(repodir, layerbranch.vcs_subdir)
            layerdir_start = os.path.normpath(layerdir) + os.sep

            layerrecipes = Recipe.objects.filter(layerbranch=layerbranch)
            layermachines = Machine.objects.filter(layerbranch=layerbranch)
            layerdistros = Distro.objects.filter(layerbranch=layerbranch)
            layerappends = BBAppend.objects.filter(layerbranch=layerbranch)
            layerclasses = BBClass.objects.filter(layerbranch=layerbranch)
            layerincfiles = IncFile.objects.filter(layerbranch=layerbranch)
            if layerbranch.vcs_last_rev != topcommit.hexsha or options.reload or options.initial:
                # Check out appropriate branch
                if not options.nocheckout:
                    utils.checkout_layer_branch(layerbranch, repodir, logger=logger)

                logger.info("Collecting data for layer %s on branch %s" % (layer.name, branchdesc))
                try:
                    (tinfoil, tempdir) = recipeparse.init_parser(settings, branch, bitbakepath, nocheckout=options.nocheckout, logger=logger)
                except recipeparse.RecipeParseError as e:
                    logger.error(str(e))
                    sys.exit(1)
                logger.debug('Using temp directory %s' % tempdir)
                # Clear the default value of SUMMARY so that we can use DESCRIPTION instead if it hasn't been set
                tinfoil.config_data.setVar('SUMMARY', '')
                # Clear the default value of DESCRIPTION so that we can see where it's not set
                tinfoil.config_data.setVar('DESCRIPTION', '')
                # Clear the default value of HOMEPAGE ('unknown')
                tinfoil.config_data.setVar('HOMEPAGE', '')
                # Set a blank value for LICENSE so that it doesn't cause the parser to die (e.g. with meta-ti -
                # why won't they just fix that?!)
                tinfoil.config_data.setVar('LICENSE', '')

                layerconfparser = layerconfparse.LayerConfParse(logger=logger, tinfoil=tinfoil)
                layer_config_data = layerconfparser.parse_layer(layerdir)
                if not layer_config_data:
                    logger.info("Skipping update of layer %s for branch %s - conf/layer.conf may have parse issues" % (layer.name, branchdesc))
                    layerconfparser.shutdown()
                    sys.exit(1)
                utils.set_layerbranch_collection_version(layerbranch, layer_config_data, logger=logger)
                if options.initial:
                    # Use print() rather than logger.info() since "-q" makes it print nothing.
                    for i in ["BBFILE_COLLECTIONS", "LAYERVERSION", "LAYERDEPENDS", "LAYERRECOMMENDS"]:
                        print('%s = "%s"' % (i, utils.get_layer_var(layer_config_data, i, logger)))
                    sys.exit(0)

                # Set up for recording patch info
                utils.setup_core_layer_sys_path(settings, branch.name)
                skip_patches = False
                try:
                    import oe.recipeutils
                except ImportError:
                    logger.warn('Failed to find lib/oe/recipeutils.py in layers - patch information will not be collected')
                    skip_patches = True

                utils.add_dependencies(layerbranch, layer_config_data, logger=logger)
                utils.add_recommends(layerbranch, layer_config_data, logger=logger)
                layerbranch.save()

                try:
                    config_data_copy = recipeparse.setup_layer(tinfoil.config_data, fetchdir, layerdir, layer, layerbranch, logger)
                except recipeparse.RecipeParseError as e:
                    logger.error(str(e))
                    sys.exit(1)

                if layerbranch.vcs_last_rev and not options.reload:
                    try:
                        diff = repo.commit(layerbranch.vcs_last_rev).diff(topcommit)
                    except Exception as e:
                        logger.warn("Unable to get diff from last commit hash for layer %s - falling back to slow update: %s" % (layer.name, str(e)))
                        diff = None
                else:
                    diff = None

                # We handle recipes specially to try to preserve the same id
                # when recipe upgrades happen (so that if a user bookmarks a
                # recipe page it remains valid)
                layerrecipes_delete = []
                layerrecipes_add = []

                # Check if any paths should be ignored because there are layers within this layer
                removedirs = []
                for root, dirs, files in os.walk(layerdir):
                    for diritem in dirs:
                        if os.path.exists(os.path.join(root, diritem, 'conf', 'layer.conf')):
                            removedirs.append(os.path.join(root, diritem) + os.sep)

                if diff:
                    # Apply git changes to existing recipe list

                    if layerbranch.vcs_subdir:
                        subdir_start = os.path.normpath(layerbranch.vcs_subdir) + os.sep
                    else:
                        subdir_start = ""

                    updatedrecipes = set()
                    dirtyrecipes = set()
                    other_deletes = []
                    other_adds = []
                    for diffitem in diff.iter_change_type('R'):
                        oldpath = diffitem.a_blob.path
                        newpath = diffitem.b_blob.path
                        skip = False
                        for removedir in removedirs:
                            # FIXME what about files moved into removedirs?
                            if oldpath.startswith(removedir):
                                skip = True
                                break
                        if skip:
                            continue
                        if oldpath.startswith(subdir_start):
                            if not newpath.startswith(subdir_start):
                                logger.debug("Treating rename of %s to %s as a delete since new path is outside layer" % (oldpath, newpath))
                                other_deletes.append(diffitem)
                                continue
                            (oldtypename, oldfilepath, oldfilename) = recipeparse.detect_file_type(oldpath, subdir_start)
                            (newtypename, newfilepath, newfilename) = recipeparse.detect_file_type(newpath, subdir_start)
                            if oldtypename != newtypename:
                                # This is most likely to be a .inc file renamed to a .bb - and since
                                # there may be another recipe deleted at the same time we probably want
                                # to consider that, so just treat it as a delete and an add
                                logger.debug("Treating rename of %s to %s as a delete and add (since type changed)" % (oldpath, newpath))
                                other_deletes.append(diffitem)
                                other_adds.append(diffitem)
                            elif oldtypename == 'recipe':
                                results = layerrecipes.filter(filepath=oldfilepath).filter(filename=oldfilename)
                                if len(results):
                                    recipe = results[0]
                                    logger.debug("Rename recipe %s to %s" % (recipe, newpath))
                                    recipe.filepath = newfilepath
                                    recipe.filename = newfilename
                                    recipe.save()
                                    update_recipe_file(tinfoil, config_data_copy, os.path.join(layerdir, newfilepath), recipe, layerdir_start, repodir, options.stop_on_error, skip_patches)
                                    updatedrecipes.add(os.path.join(oldfilepath, oldfilename))
                                    updatedrecipes.add(os.path.join(newfilepath, newfilename))
                                else:
                                    logger.warn("Renamed recipe %s could not be found" % oldpath)
                                    other_adds.append(diffitem)
                            elif oldtypename == 'bbappend':
                                results = layerappends.filter(filepath=oldfilepath).filter(filename=oldfilename)
                                if len(results):
                                    logger.debug("Rename bbappend %s to %s" % (results[0], os.path.join(newfilepath, newfilename)))
                                    results[0].filepath = newfilepath
                                    results[0].filename = newfilename
                                    results[0].save()
                                else:
                                    logger.warn("Renamed bbappend %s could not be found" % oldpath)
                                    other_adds.append(diffitem)
                            elif oldtypename == 'machine':
                                results = layermachines.filter(name=oldfilename)
                                if len(results):
                                    logger.debug("Rename machine %s to %s" % (results[0], newfilename))
                                    results[0].name = newfilename
                                    results[0].save()
                                else:
                                    logger.warn("Renamed machine %s could not be found" % oldpath)
                                    other_adds.append(diffitem)
                            elif oldtypename == 'distro':
                                results = layerdistros.filter(name=oldfilename)
                                if len(results):
                                    logger.debug("Rename distro %s to %s" % (results[0], newfilename))
                                    results[0].name = newfilename
                                    results[0].save()
                                else:
                                    logger.warn("Renamed distro %s could not be found" % oldpath)
                                    other_adds.append(diffitem)
                            elif oldtypename == 'bbclass':
                                results = layerclasses.filter(name=oldfilename)
                                if len(results):
                                    logger.debug("Rename class %s to %s" % (results[0], newfilename))
                                    results[0].name = newfilename
                                    results[0].save()
                                else:
                                    logger.warn("Renamed class %s could not be found" % oldpath)
                                    other_adds.append(diffitem)
                            elif oldtypename == 'incfile':
                                results = layerincfiles.filter(path=os.path.join(oldfilepath, oldfilename))
                                if len(results):
                                    logger.debug("Rename inc file %s to %s" % (results[0], newfilename))
                                    results[0].name = newfilename
                                    results[0].save()
                                else:
                                    logger.warn("Renamed inc file %s could not be found" % oldpath)
                                    other_adds.append(diffitem)

                            deps = RecipeFileDependency.objects.filter(layerbranch=layerbranch).filter(path=oldpath)
                            for dep in deps:
                                dirtyrecipes.add(dep.recipe)


                    for diffitem in itertools.chain(diff.iter_change_type('D'), other_deletes):
                        path = diffitem.a_blob.path
                        if path.startswith(subdir_start):
                            skip = False
                            for removedir in removedirs:
                                if path.startswith(removedir):
                                    skip = True
                                    break
                            if skip:
                                continue
                            (typename, filepath, filename) = recipeparse.detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                values = layerrecipes.filter(filepath=filepath).filter(filename=filename).values('id', 'filepath', 'filename', 'pn')
                                if len(values):
                                    layerrecipes_delete.append(values[0])
                                    logger.debug("Mark %s for deletion" % values[0])
                                    updatedrecipes.add(os.path.join(values[0]['filepath'], values[0]['filename']))
                                else:
                                    logger.warn("Deleted recipe %s could not be found" % path)
                            elif typename == 'bbappend':
                                layerappends.filter(filepath=filepath).filter(filename=filename).delete()
                            elif typename == 'machine':
                                layermachines.filter(name=filename).delete()
                            elif typename == 'distro':
                                layerdistros.filter(name=filename).delete()
                            elif typename == 'bbclass':
                                layerclasses.filter(name=filename).delete()
                            elif typename == 'incfile':
                                layerincfiles.filter(path=os.path.join(filepath, filename)).delete()

                    for diffitem in itertools.chain(diff.iter_change_type('A'), other_adds):
                        path = diffitem.b_blob.path
                        if path.startswith(subdir_start):
                            skip = False
                            for removedir in removedirs:
                                if path.startswith(removedir):
                                    skip = True
                                    break
                            if skip:
                                continue
                            (typename, filepath, filename) = recipeparse.detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                layerrecipes_add.append(os.path.join(repodir, path))
                                logger.debug("Mark %s for addition" % path)
                                updatedrecipes.add(os.path.join(filepath, filename))
                            elif typename == 'bbappend':
                                append = BBAppend()
                                append.layerbranch = layerbranch
                                append.filename = filename
                                append.filepath = filepath
                                append.save()
                            elif typename == 'machine':
                                machine = Machine()
                                machine.layerbranch = layerbranch
                                machine.name = filename
                                update_machine_conf_file(os.path.join(repodir, path), machine)
                                machine.save()
                            elif typename == 'distro':
                                distro = Distro()
                                distro.layerbranch = layerbranch
                                distro.name = filename
                                update_distro_conf_file(os.path.join(repodir, path), distro, config_data_copy)
                                distro.save()
                            elif typename == 'bbclass':
                                bbclass = BBClass()
                                bbclass.layerbranch = layerbranch
                                bbclass.name = filename
                                bbclass.save()
                            elif typename == 'incfile':
                                incfile = IncFile()
                                incfile.layerbranch = layerbranch
                                incfile.path = os.path.join(filepath, filename)
                                incfile.save()

                    for diffitem in diff.iter_change_type('M'):
                        path = diffitem.b_blob.path
                        if path.startswith(subdir_start):
                            skip = False
                            for removedir in removedirs:
                                if path.startswith(removedir):
                                    skip = True
                                    break
                            if skip:
                                continue
                            (typename, filepath, filename) = recipeparse.detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                logger.debug("Mark %s for update" % path)
                                results = layerrecipes.filter(filepath=filepath).filter(filename=filename)[:1]
                                if results:
                                    recipe = results[0]
                                    update_recipe_file(tinfoil, config_data_copy, os.path.join(layerdir, filepath), recipe, layerdir_start, repodir, options.stop_on_error, skip_patches)
                                    recipe.save()
                                    updatedrecipes.add(recipe.full_path())
                            elif typename == 'machine':
                                results = layermachines.filter(name=filename)
                                if results:
                                    machine = results[0]
                                    update_machine_conf_file(os.path.join(repodir, path), machine)
                                    machine.save()
                            elif typename == 'distro':
                                results = layerdistros.filter(name=filename)
                                if results:
                                    distro = results[0]
                                    update_distro_conf_file(os.path.join(repodir, path), distro, config_data_copy)
                                    distro.save()

                            deps = RecipeFileDependency.objects.filter(layerbranch=layerbranch).filter(path=path)
                            for dep in deps:
                                dirtyrecipes.add(dep.recipe)

                    for recipe in dirtyrecipes:
                        if not recipe.full_path() in updatedrecipes:
                            update_recipe_file(tinfoil, config_data_copy, os.path.join(layerdir, recipe.filepath), recipe, layerdir_start, repodir, options.stop_on_error, skip_patches)
                else:
                    # Collect recipe data from scratch

                    layerrecipe_fns = []
                    if options.fullreload:
                        layerrecipes.delete()
                    else:
                        # First, check which recipes still exist
                        layerrecipe_values = layerrecipes.values('id', 'filepath', 'filename', 'pn')
                        for v in layerrecipe_values:
                            if v['filepath'].startswith('../'):
                                # FIXME: These recipes were present due to a bug (not handling renames
                                # to paths outside the layer) - this can be removed at some point in the future
                                preserve = False
                            else:
                                root = os.path.join(layerdir, v['filepath'])
                                fullpath = os.path.join(root, v['filename'])
                                if os.path.exists(fullpath):
                                    preserve = True
                                    for removedir in removedirs:
                                        if fullpath.startswith(removedir):
                                            preserve = False
                                            break
                                else:
                                    preserve = False

                            if preserve:
                                # Recipe still exists, update it
                                results = layerrecipes.filter(id=v['id'])[:1]
                                recipe = results[0]
                                update_recipe_file(tinfoil, config_data_copy, root, recipe, layerdir_start, repodir, options.stop_on_error, skip_patches)
                            else:
                                # Recipe no longer exists, mark it for later on
                                layerrecipes_delete.append(v)
                            layerrecipe_fns.append(fullpath)

                    layermachines.delete()
                    layerdistros.delete()
                    layerappends.delete()
                    layerclasses.delete()
                    for root, dirs, files in os.walk(layerdir):
                        if '.git' in dirs:
                            dirs.remove('.git')
                        for diritem in dirs[:]:
                            fullpath = os.path.join(root, diritem) + os.sep
                            if fullpath in removedirs:
                                dirs.remove(diritem)
                        for f in files:
                            fullpath = os.path.join(root, f)
                            (typename, _, filename) = recipeparse.detect_file_type(fullpath, layerdir_start)
                            if typename == 'recipe':
                                if fullpath not in layerrecipe_fns:
                                    layerrecipes_add.append(fullpath)
                            elif typename == 'bbappend':
                                append = BBAppend()
                                append.layerbranch = layerbranch
                                append.filename = f
                                append.filepath = os.path.relpath(root, layerdir)
                                append.save()
                            elif typename == 'machine':
                                machine = Machine()
                                machine.layerbranch = layerbranch
                                machine.name = filename
                                update_machine_conf_file(fullpath, machine)
                                machine.save()
                            elif typename == 'distro':
                                distro = Distro()
                                distro.layerbranch = layerbranch
                                distro.name = filename
                                update_distro_conf_file(fullpath, distro, config_data_copy)
                                distro.save()
                            elif typename == 'bbclass':
                                bbclass = BBClass()
                                bbclass.layerbranch = layerbranch
                                bbclass.name = filename
                                bbclass.save()
                            elif typename == 'incfile':
                                incfile = IncFile()
                                incfile.layerbranch = layerbranch
                                incfile.path = os.path.relpath(fullpath, layerdir)
                                incfile.save()

                for added in layerrecipes_add:
                    # This is good enough without actually parsing the file
                    (pn, pv) = split_recipe_fn(added)
                    oldid = -1
                    for deleted in layerrecipes_delete:
                        if deleted['pn'] == pn:
                            oldid = deleted['id']
                            layerrecipes_delete.remove(deleted)
                            break
                    if oldid > -1:
                        # Reclaim a record we would have deleted
                        results = Recipe.objects.filter(id=oldid)[:1]
                        recipe = results[0]
                        logger.debug("Reclaim %s for %s %s" % (recipe, pn, pv))
                    else:
                        # Create new record
                        logger.debug("Add new recipe %s" % added)
                        recipe = Recipe()
                    recipe.layerbranch = layerbranch
                    recipe.filename = os.path.basename(added)
                    root = os.path.dirname(added)
                    recipe.filepath = os.path.relpath(root, layerdir)
                    update_recipe_file(tinfoil, config_data_copy, root, recipe, layerdir_start, repodir, options.stop_on_error, skip_patches)
                    recipe.save()

                for deleted in layerrecipes_delete:
                    logger.debug("Delete %s" % deleted)
                    results = Recipe.objects.filter(id=deleted['id'])[:1]
                    recipe = results[0]
                    recipe.delete()

                # Save repo info
                layerbranch.vcs_last_rev = topcommit.hexsha
                layerbranch.vcs_last_commit = datetime.fromtimestamp(topcommit.committed_date)
            else:
                logger.info("Layer %s is already up-to-date for branch %s" % (layer.name, branchdesc))

            layerbranch.vcs_last_fetch = datetime.now()
            layerbranch.save()

            if options.dryrun:
                raise DryRunRollbackException()


    except KeyboardInterrupt:
        logger.warn("Update interrupted, changes to %s rolled back" % layer.name)
        sys.exit(254)
    except SystemExit:
        raise
    except DryRunRollbackException:
        pass
    except:
        import traceback
        logger.error(traceback.format_exc().rstrip())
        sys.exit(1)
    finally:
        if tinfoil and (LooseVersion(bb.__version__) > LooseVersion("1.27")):
            tinfoil.shutdown()

    if tempdir:
        if options.keep_temp:
            logger.debug('Preserving temp directory %s' % tempdir)
        else:
            logger.debug('Deleting temp directory')
            utils.rmtree_force(tempdir)
    sys.exit(0)


if __name__ == "__main__":
    main()
