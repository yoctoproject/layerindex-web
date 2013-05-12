#!/usr/bin/env python

# Fetch layer repositories and update layer index database
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os.path
import optparse
import logging
import subprocess
from datetime import datetime
import fnmatch
import re
import tempfile
import shutil
from distutils.version import LooseVersion

def logger_create():
    logger = logging.getLogger("LayerIndexUpdate")
    loggerhandler = logging.StreamHandler()
    loggerhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(loggerhandler)
    logger.setLevel(logging.INFO)
    return logger

logger = logger_create()

# Ensure PythonGit is installed (buildhistory_analysis needs it)
try:
    import git
except ImportError:
    logger.error("Please install PythonGit 0.3.1 or later in order to use this script")
    sys.exit(1)


def runcmd(cmd,destdir=None,printerr=True):
    """
        execute command, raise CalledProcessError if fail
        return output if succeed
    """
    logger.debug("run cmd '%s' in %s" % (cmd, os.getcwd() if destdir is None else destdir))
    out = os.tmpfile()
    try:
        subprocess.check_call(cmd, stdout=out, stderr=out, cwd=destdir, shell=True)
    except subprocess.CalledProcessError,e:
        out.seek(0)
        if printerr:
            logger.error("%s" % out.read())
        raise e

    out.seek(0)
    output = out.read()
    logger.debug("output: %s" % output.rstrip() )
    return output


machine_conf_re = re.compile(r'conf/machine/([^/.]*).conf$')
bbclass_re = re.compile(r'classes/([^/.]*).bbclass$')
def detect_file_type(path, subdir_start):
    typename = None
    if fnmatch.fnmatch(path, "*.bb"):
        typename = 'recipe'
    elif fnmatch.fnmatch(path, "*.bbappend"):
        typename = 'bbappend'
    else:
        # Check if it's a machine conf file
        subpath = path[len(subdir_start):]
        res = machine_conf_re.match(subpath)
        if res:
            typename = 'machine'
            return (typename, None, res.group(1))
        else:
            res = bbclass_re.match(subpath)
            if res:
                typename = 'bbclass'
                return (typename, None, res.group(1))

    if typename == 'recipe' or typename == 'bbappend':
        if subdir_start:
            filepath = os.path.relpath(os.path.dirname(path), subdir_start)
        else:
            filepath = os.path.dirname(path)
        return (typename, filepath, os.path.basename(path))

    return (None, None, None)


def check_machine_conf(path, subdir_start):
    subpath = path[len(subdir_start):]
    res = conf_re.match(subpath)
    if res:
        return res.group(1)
    return None

def update_recipe_file(data, path, recipe, layerdir_start, repodir):
    fn = str(os.path.join(path, recipe.filename))
    try:
        logger.debug('Updating recipe %s' % fn)
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
        recipe.save()

        # Get file dependencies within this layer
        deps = envdata.getVar('__depends', True)
        filedeps = []
        for depstr, date in deps:
            found = False
            if depstr.startswith(layerdir_start) and not depstr.endswith('/conf/layer.conf'):
                filedeps.append(os.path.relpath(depstr, repodir))
        from layerindex.models import RecipeFileDependency
        RecipeFileDependency.objects.filter(recipe=recipe).delete()
        for filedep in filedeps:
            recipedep = RecipeFileDependency()
            recipedep.layerbranch = recipe.layerbranch
            recipedep.recipe = recipe
            recipedep.path = filedep
            recipedep.save()
    except KeyboardInterrupt:
        raise
    except BaseException as e:
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

def parse_layer_conf(layerdir, data):
    data.setVar('LAYERDIR', str(layerdir))
    if hasattr(bb, "cookerdata"):
        # Newer BitBake
        data = bb.cookerdata.parse_config_file(os.path.join(layerdir, "conf", "layer.conf"), data)
    else:
        # Older BitBake (1.18 and below)
        data = bb.cooker._parse(os.path.join(layerdir, "conf", "layer.conf"), data)
    data.expandVarref('LAYERDIR')

def get_branch(branchname):
    from layerindex.models import Branch
    res = list(Branch.objects.filter(name=branchname)[:1])
    if res:
        return res[0]
    return None

def get_layer(layername):
    from layerindex.models import LayerItem
    res = list(LayerItem.objects.filter(name=layername)[:1])
    if res:
        return res[0]
    return None

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
            help = "Specify layers to update (use commas to separate multiple). Default is all published layers.",
            action="store", dest="layers")
    parser.add_option("-r", "--reload",
            help = "Discard existing recipe data and fetch it from scratch",
            action="store_true", dest="reload")
    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("-x", "--nofetch",
            help = "Don't fetch repositories",
            action="store_true", dest="nofetch")
    parser.add_option("", "--nocheckout",
            help = "Don't check out branches",
            action="store_true", dest="nocheckout")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")


    options, args = parser.parse_args(sys.argv)
    if len(args) > 1:
        logger.error('unexpected argument "%s"' % args[1])
        parser.print_help()
        sys.exit(1)

    # Get access to our Django model
    newpath = os.path.abspath(os.path.dirname(os.path.abspath(sys.argv[0])) + '/..')
    sys.path.append(newpath)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

    from django.core.management import setup_environ
    from django.conf import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, RecipeFileDependency, Machine, BBAppend, BBClass
    from django.db import transaction
    import settings

    setup_environ(settings)

    logger.setLevel(options.loglevel)

    branch = get_branch(options.branch)
    if not branch:
        logger.error("Specified branch %s is not valid" % options.branch)
        sys.exit(1)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if options.layers:
        layerquery = LayerItem.objects.filter(name__in=options.layers.split(','))
        if layerquery.count() == 0:
            logger.error('No layers matching specified query "%s"' % options.layers)
            sys.exit(1)
    else:
        layerquery = LayerItem.objects.filter(status='P')
        if layerquery.count() == 0:
            logger.info("No published layers to update")
            sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)
    fetchedrepos = []
    failedrepos = []

    bitbakepath = os.path.join(fetchdir, 'bitbake')

    if not options.nofetch:
        # Fetch latest metadata from repositories
        for layer in layerquery:
            # Handle multiple layers in a single repo
            urldir = layer.get_fetch_dir()
            repodir = os.path.join(fetchdir, urldir)
            if not (layer.vcs_url in fetchedrepos or layer.vcs_url in failedrepos):
                logger.info("Fetching remote repository %s" % layer.vcs_url)
                out = None
                try:
                    if not os.path.exists(repodir):
                        out = runcmd("git clone %s %s" % (layer.vcs_url, urldir), fetchdir)
                    else:
                        out = runcmd("git fetch", repodir)
                except Exception as e:
                    logger.error("Fetch of layer %s failed: %s" % (layer.name, str(e)))
                    failedrepos.append(layer.vcs_url)
                    continue
                fetchedrepos.append(layer.vcs_url)

        if not fetchedrepos:
            logger.error("No repositories could be fetched, exiting")
            sys.exit(1)

        logger.info("Fetching bitbake from remote repository %s" % settings.BITBAKE_REPO_URL)
        if not os.path.exists(bitbakepath):
            out = runcmd("git clone %s %s" % (settings.BITBAKE_REPO_URL, 'bitbake'), fetchdir)
        else:
            out = runcmd("git fetch", bitbakepath)

    if not options.nocheckout:
        # Check out the branch of BitBake appropriate for this branch and clean out any stale files (e.g. *.pyc)
        out = runcmd("git checkout origin/%s" % branch.bitbake_branch, bitbakepath)
        out = runcmd("git clean -f -x", bitbakepath)

    # Skip sanity checks
    os.environ['BB_ENV_EXTRAWHITE'] = 'DISABLE_SANITY_CHECKS'
    os.environ['DISABLE_SANITY_CHECKS'] = '1'

    # Ensure we have OE-Core set up to get some base configuration
    core_layer = get_layer(settings.CORE_LAYER_NAME)
    if not core_layer:
        logger.error("Unable to find core layer %s in database; check CORE_LAYER_NAME setting" % settings.CORE_LAYER_NAME)
        sys.exit(1)
    core_layerbranch = core_layer.get_layerbranch(options.branch)
    if core_layerbranch:
        core_subdir = core_layerbranch.vcs_subdir
    else:
        core_subdir = 'meta'
    core_urldir = core_layer.get_fetch_dir()
    core_repodir = os.path.join(fetchdir, core_urldir)
    core_layerdir = os.path.join(core_repodir, core_subdir)
    if not options.nocheckout:
        out = runcmd("git checkout origin/%s" % options.branch, core_repodir)
        out = runcmd("git clean -f -x", core_repodir)
    # The directory above where this script exists should contain our conf/layer.conf,
    # so add it to BBPATH along with the core layer directory
    confparentdir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    os.environ['BBPATH'] = str("%s:%s" % (confparentdir, core_layerdir))

    # Change into a temporary directory so we don't write the cache and other files to the current dir
    if not os.path.exists(settings.TEMP_BASE_DIR):
        os.makedirs(settings.TEMP_BASE_DIR)
    tempdir = tempfile.mkdtemp(dir=settings.TEMP_BASE_DIR)
    os.chdir(tempdir)

    sys.path.extend([bitbakepath + '/lib'])
    import bb.tinfoil
    import bb.cooker
    tinfoil = bb.tinfoil.Tinfoil()
    tinfoil.prepare(config_only = True)

    # Clear the default value of SUMMARY so that we can use DESCRIPTION instead if it hasn't been set
    tinfoil.config_data.setVar('SUMMARY', '')
    # Clear the default value of DESCRIPTION so that we can see where it's not set
    tinfoil.config_data.setVar('DESCRIPTION', '')
    # Clear the default value of HOMEPAGE ('unknown')
    tinfoil.config_data.setVar('HOMEPAGE', '')
    # Set a blank value for LICENSE so that it doesn't cause the parser to die (e.g. with meta-ti -
    # why won't they just fix that?!)
    tinfoil.config_data.setVar('LICENSE', '')

    # Ensure TMPDIR exists (or insane.bbclass will blow up trying to write to the QA log)
    oe_tmpdir = tinfoil.config_data.getVar('TMPDIR', True)
    os.makedirs(oe_tmpdir)

    # Process and extract data from each layer
    for layer in layerquery:
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
            urldir = layer.get_fetch_dir()
            repodir = os.path.join(fetchdir, urldir)
            if layer.vcs_url in failedrepos:
                logger.info("Skipping update of layer %s as fetch of repository %s failed" % (layer.name, layer.vcs_url))
                transaction.rollback()
                continue

            # Collect repo info
            repo = git.Repo(repodir)
            assert repo.bare == False
            try:
                topcommit = repo.commit('origin/%s' % options.branch)
            except:
                logger.info("Skipping update of layer %s - branch %s doesn't exist" % (layer.name, options.branch))
                transaction.rollback()
                continue

            layerbranch = layer.get_layerbranch(options.branch)
            if not layerbranch:
                # LayerBranch doesn't exist for this branch, create it
                layerbranch = LayerBranch()
                layerbranch.layer = layer
                layerbranch.branch = branch
                layerbranch_master = layer.get_layerbranch('master')
                if layerbranch_master:
                    layerbranch.vcs_subdir = layerbranch_master.vcs_subdir
                layerbranch.save()
                if layerbranch_master:
                    for maintainer in layerbranch_master.layermaintainer_set.all():
                        maintainer.pk = None
                        maintainer.id = None
                        maintainer.layerbranch = layerbranch
                        maintainer.save()
                    for dep in layerbranch_master.dependencies_set.all():
                        dep.pk = None
                        dep.id = None
                        dep.layerbranch = layerbranch
                        dep.save()

            if layerbranch.vcs_subdir:
                # Find latest commit in subdirectory
                # A bit odd to do it this way but apparently there's no other way in the GitPython API
                for commit in repo.iter_commits('origin/%s' % options.branch, paths=layerbranch.vcs_subdir):
                    topcommit = commit
                    break

            layerdir = os.path.join(repodir, layerbranch.vcs_subdir)
            layerdir_start = os.path.normpath(layerdir) + os.sep
            layerrecipes = Recipe.objects.filter(layerbranch=layerbranch)
            layermachines = Machine.objects.filter(layerbranch=layerbranch)
            layerappends = BBAppend.objects.filter(layerbranch=layerbranch)
            layerclasses = BBClass.objects.filter(layerbranch=layerbranch)
            if layerbranch.vcs_last_rev != topcommit.hexsha or options.reload:
                # Check out appropriate branch
                if not options.nocheckout:
                    out = runcmd("git checkout origin/%s" % options.branch, repodir)
                    out = runcmd("git clean -f -x", repodir)

                if not os.path.exists(layerdir):
                    if options.branch == 'master':
                        logger.error("Subdirectory for layer %s does not exist on master branch!" % layer.name)
                        transaction.rollback()
                        continue
                    else:
                        logger.info("Skipping update of layer %s for branch %s - subdirectory does not exist on this branch" % (layer.name, options.branch))
                        transaction.rollback()
                        continue

                if not os.path.exists(os.path.join(layerdir, 'conf/layer.conf')):
                    logger.error("conf/layer.conf not found for layer %s - is subdirectory set correctly?" % layer.name)
                    transaction.rollback()
                    continue

                logger.info("Collecting data for layer %s on branch %s" % (layer.name, options.branch))

                # Parse layer.conf files for this layer and its dependencies
                # This is necessary not just because BBPATH needs to be set in order
                # for include/require/inherit to work outside of the current directory
                # or across layers, but also because custom variable values might be
                # set in layer.conf.

                config_data_copy = bb.data.createCopy(tinfoil.config_data)
                parse_layer_conf(layerdir, config_data_copy)
                for dep in layerbranch.dependencies_set.all():
                    depurldir = dep.dependency.get_fetch_dir()
                    deprepodir = os.path.join(fetchdir, depurldir)
                    deplayerbranch = dep.dependency.get_layerbranch(options.branch)
                    if not deplayerbranch:
                        logger.error('Dependency %s of layer %s does not have branch record for branch %s' % (dep.dependency.name, layer.name, options.branch))
                        transaction.rollback()
                        continue
                    deplayerdir = os.path.join(deprepodir, deplayerbranch.vcs_subdir)
                    parse_layer_conf(deplayerdir, config_data_copy)
                config_data_copy.delVar('LAYERDIR')

                if layerbranch.vcs_last_rev and not options.reload:
                    try:
                        diff = repo.commit(layerbranch.vcs_last_rev).diff(topcommit)
                    except Exception as e:
                        logger.warn("Unable to get diff from last commit hash for layer %s - falling back to slow update: %s" % (layer.name, str(e)))
                        diff = None
                else:
                    diff = None

                if diff:
                    # Apply git changes to existing recipe list

                    if layerbranch.vcs_subdir:
                        subdir_start = os.path.normpath(layerbranch.vcs_subdir) + os.sep
                    else:
                        subdir_start = ""

                    updatedrecipes = set()
                    for d in diff.iter_change_type('D'):
                        path = d.a_blob.path
                        if path.startswith(subdir_start):
                            (typename, filepath, filename) = detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                layerrecipes.filter(filepath=filepath).filter(filename=filename).delete()
                            elif typename == 'bbappend':
                                layerappends.filter(filepath=filepath).filter(filename=filename).delete()
                            elif typename == 'machine':
                                layermachines.filter(name=filename).delete()
                            elif typename == 'bbclass':
                                layerclasses.filter(name=filename).delete()

                    for d in diff.iter_change_type('A'):
                        path = d.b_blob.path
                        if path.startswith(subdir_start):
                            (typename, filepath, filename) = detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                recipe = Recipe()
                                recipe.layerbranch = layerbranch
                                recipe.filename = filename
                                recipe.filepath = filepath
                                update_recipe_file(config_data_copy, os.path.join(layerdir, filepath), recipe, layerdir_start, repodir)
                                recipe.save()
                                updatedrecipes.add(recipe)
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
                            elif typename == 'bbclass':
                                bbclass = BBClass()
                                bbclass.layerbranch = layerbranch
                                bbclass.name = filename
                                bbclass.save()

                    dirtyrecipes = set()
                    for d in diff.iter_change_type('M'):
                        path = d.a_blob.path
                        if path.startswith(subdir_start):
                            (typename, filepath, filename) = detect_file_type(path, subdir_start)
                            if typename == 'recipe':
                                results = layerrecipes.filter(filepath=filepath).filter(filename=filename)[:1]
                                if results:
                                    recipe = results[0]
                                    update_recipe_file(config_data_copy, os.path.join(layerdir, filepath), recipe, layerdir_start, repodir)
                                    recipe.save()
                                    updatedrecipes.add(recipe)
                            elif typename == 'machine':
                                results = layermachines.filter(name=filename)
                                if results:
                                    machine = results[0]
                                    update_machine_conf_file(os.path.join(repodir, path), machine)
                                    machine.save()

                            deps = RecipeFileDependency.objects.filter(layerbranch=layerbranch).filter(path=path)
                            for dep in deps:
                                dirtyrecipes.add(dep.recipe)

                    dirtyrecipes -= updatedrecipes
                    for recipe in dirtyrecipes:
                        update_recipe_file(config_data_copy, os.path.join(layerdir, recipe.filepath), recipe, layerdir_start, repodir)
                else:
                    # Collect recipe data from scratch
                    layerrecipes.delete()
                    layermachines.delete()
                    layerappends.delete()
                    layerclasses.delete()
                    for root, dirs, files in os.walk(layerdir):
                        if '.git' in dirs:
                            dirs.remove('.git')
                        for f in files:
                            fullpath = os.path.join(root, f)
                            (typename, _, filename) = detect_file_type(fullpath, layerdir_start)
                            if typename == 'recipe':
                                recipe = Recipe()
                                recipe.layerbranch = layerbranch
                                recipe.filename = f
                                recipe.filepath = os.path.relpath(root, layerdir)
                                update_recipe_file(config_data_copy, root, recipe, layerdir_start, repodir)
                                recipe.save()
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
                            elif typename == 'bbclass':
                                bbclass = BBClass()
                                bbclass.layerbranch = layerbranch
                                bbclass.name = filename
                                bbclass.save()

                # Save repo info
                layerbranch.vcs_last_rev = topcommit.hexsha
                layerbranch.vcs_last_commit = datetime.fromtimestamp(topcommit.committed_date)
            else:
                logger.info("Layer %s is already up-to-date for branch %s" % (layer.name, options.branch))

            layerbranch.vcs_last_fetch = datetime.now()
            layerbranch.save()

            if options.dryrun:
                transaction.rollback()
            else:
                transaction.commit()
        except:
            import traceback
            traceback.print_exc()
            transaction.rollback()
        finally:
            transaction.leave_transaction_management()

    shutil.rmtree(tempdir)
    sys.exit(0)


if __name__ == "__main__":
    main()
