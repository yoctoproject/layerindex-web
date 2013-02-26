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

def sanitise_path(inpath):
    outpath = ""
    for c in inpath:
        if c in '/ .=+?:':
            outpath += "_"
        else:
            outpath += c
    return outpath


def split_bb_file_path(recipe_path, subdir_start):
    if fnmatch.fnmatch(recipe_path, "*.bb"):
        if subdir_start:
            filepath = os.path.relpath(os.path.dirname(recipe_path), subdir_start)
        else:
            filepath = os.path.dirname(recipe_path)
        return (filepath, os.path.basename(recipe_path))
    return (None, None)

conf_re = re.compile(r'conf/machine/([^/.]*).conf$')
def check_machine_conf(path):
    res = conf_re.search(path)
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
            recipedep.layer = recipe.layer
            recipedep.recipe = recipe
            recipedep.path = filedep
            recipedep.save()
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        logger.info("Unable to read %s: %s", fn, str(e))

def update_machine_conf_file(path, machine):
    logger.debug('Updating machine %s' % path)
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#@DESCRIPTION:'):
                desc = line[14:].strip()
                desc = re.sub(r'Machine configuration for (the )*', '', desc)
                machine.description = desc
                break

def parse_layer_conf(layerdir, data):
    data.setVar('LAYERDIR', str(layerdir))
    data = bb.cooker._parse(os.path.join(layerdir, "conf", "layer.conf"), data)
    data.expandVarref('LAYERDIR')

def setup_bitbake_path(basepath):
    # Set path to bitbake lib dir
    bitbakedir_env = os.environ.get('BITBAKEDIR', '')
    if bitbakedir_env and os.path.exists(bitbakedir_env + '/lib/bb'):
        bitbakepath = bitbakedir_env
    elif basepath and os.path.exists(basepath + '/bitbake/lib/bb'):
        bitbakepath = basepath + '/bitbake'
    elif basepath and os.path.exists(basepath + '/../bitbake/lib/bb'):
        bitbakepath = os.path.abspath(basepath + '/../bitbake')
    else:
        # look for bitbake/bin dir in PATH
        bitbakepath = None
        for pth in os.environ['PATH'].split(':'):
            if os.path.exists(os.path.join(pth, '../lib/bb')):
                bitbakepath = os.path.abspath(os.path.join(pth, '..'))
                break
        if not bitbakepath:
            if basepath:
                logger.error("Unable to find bitbake by searching BITBAKEDIR, specified path '%s' or its parent, or PATH" % basepath)
            else:
                logger.error("Unable to find bitbake by searching BITBAKEDIR or PATH")
            sys.exit(1)
    return bitbakepath


def main():
    if LooseVersion(git.__version__) < '0.3.1':
        logger.error("Version of GitPython is too old, please install GitPython (python-git) 0.3.1 or later in order to use this script")
        sys.exit(1)


    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

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
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")


    options, args = parser.parse_args(sys.argv)

    # Get access to our Django model
    newpath = os.path.abspath(os.path.dirname(os.path.abspath(sys.argv[0])) + '/..')
    sys.path.append(newpath)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

    from django.core.management import setup_environ
    from django.conf import settings
    from layerindex.models import LayerItem, Recipe, RecipeFileDependency, Machine
    from django.db import transaction
    import settings

    setup_environ(settings)

    if len(sys.argv) > 1:
        basepath = os.path.abspath(sys.argv[1])
    else:
        basepath = None
    bitbakepath = setup_bitbake_path(None)

    # Skip sanity checks
    os.environ['BB_ENV_EXTRAWHITE'] = 'DISABLE_SANITY_CHECKS'
    os.environ['DISABLE_SANITY_CHECKS'] = '1'

    sys.path.extend([bitbakepath + '/lib'])
    import bb.tinfoil
    import bb.cooker
    tinfoil = bb.tinfoil.Tinfoil()
    tinfoil.prepare(config_only = True)

    logger.setLevel(options.loglevel)

    # Clear the default value of SUMMARY so that we can use DESCRIPTION instead if it hasn't been set
    tinfoil.config_data.setVar('SUMMARY', '')
    # Clear the default value of DESCRIPTION so that we can see where it's not set
    tinfoil.config_data.setVar('DESCRIPTION', '')
    # Clear the default value of HOMEPAGE ('unknown')
    tinfoil.config_data.setVar('HOMEPAGE', '')
    # Set a blank value for LICENSE so that it doesn't cause the parser to die (e.g. with meta-ti -
    # why won't they just fix that?!)
    tinfoil.config_data.setVar('LICENSE', '')

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

    if not options.nofetch:
        # Fetch latest metadata from repositories
        for layer in layerquery:
            # Handle multiple layers in a single repo
            urldir = sanitise_path(layer.vcs_url)
            repodir = os.path.join(fetchdir, urldir)
            if not layer.vcs_url in fetchedrepos:
                logger.info("Fetching remote repository %s" % layer.vcs_url)
                out = None
                try:
                    if not os.path.exists(repodir):
                        out = runcmd("git clone %s %s" % (layer.vcs_url, urldir), fetchdir)
                    else:
                        out = runcmd("git pull", repodir)
                except Exception as e:
                    logger.error("fetch failed: %s" % str(e))
                    failedrepos.append(layer.vcs_url)
                    continue
                fetchedrepos.append(layer.vcs_url)

    # Process and extract data from each layer
    for layer in layerquery:
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
            urldir = sanitise_path(layer.vcs_url)
            repodir = os.path.join(fetchdir, urldir)
            if layer.vcs_url in failedrepos:
                logger.info("Skipping update of layer %s as fetch of repository %s failed" % (layer.name, layer.vcs_url))
                transaction.rollback()
                continue
            # Collect repo info
            repo = git.Repo(repodir)
            assert repo.bare == False
            topcommit = repo.commit('master')

            layerdir = os.path.join(repodir, layer.vcs_subdir)
            layerdir_start = os.path.normpath(layerdir) + os.sep
            layerrecipes = Recipe.objects.filter(layer=layer)
            layermachines = Machine.objects.filter(layer=layer)
            if layer.vcs_last_rev != topcommit.hexsha or options.reload:
                logger.info("Collecting data for layer %s" % layer.name)

                # Parse layer.conf files for this layer and its dependencies
                # This is necessary not just because BBPATH needs to be set in order
                # for include/require/inherit to work outside of the current directory
                # or across layers, but also because custom variable values might be
                # set in layer.conf.

                config_data_copy = bb.data.createCopy(tinfoil.config_data)
                parse_layer_conf(layerdir, config_data_copy)
                for dep in layer.dependencies_set.all():
                    depurldir = sanitise_path(dep.dependency.vcs_url)
                    deprepodir = os.path.join(fetchdir, depurldir)
                    deplayerdir = os.path.join(deprepodir, dep.dependency.vcs_subdir)
                    parse_layer_conf(deplayerdir, config_data_copy)
                config_data_copy.delVar('LAYERDIR')

                if layer.vcs_last_rev and not options.reload:
                    try:
                        diff = repo.commit(layer.vcs_last_rev).diff(topcommit)
                    except Exception as e:
                        logger.warn("Unable to get diff from last commit hash for layer %s - falling back to slow update: %s" % (layer.name, str(e)))
                        diff = None
                else:
                    diff = None

                if diff:
                    # Apply git changes to existing recipe list

                    if layer.vcs_subdir:
                        subdir_start = os.path.normpath(layer.vcs_subdir) + os.sep
                    else:
                        subdir_start = ""

                    updatedrecipes = set()
                    for d in diff.iter_change_type('D'):
                        path = d.a_blob.path
                        if path.startswith(subdir_start):
                            (filepath, filename) = split_bb_file_path(path, subdir_start)
                            if filename:
                                layerrecipes.filter(filepath=filepath).filter(filename=filename).delete()
                            else:
                                machinename = check_machine_conf(path)
                                if machinename:
                                    layermachines.filter(name=machinename).delete()

                    for d in diff.iter_change_type('A'):
                        path = d.b_blob.path
                        if path.startswith(subdir_start):
                            (filepath, filename) = split_bb_file_path(path, subdir_start)
                            if filename:
                                recipe = Recipe()
                                recipe.layer = layer
                                recipe.filename = filename
                                recipe.filepath = filepath
                                update_recipe_file(config_data_copy, os.path.join(layerdir, filepath), recipe, layerdir_start, repodir)
                                recipe.save()
                                updatedrecipes.add(recipe)
                            else:
                                machinename = check_machine_conf(path)
                                if machinename:
                                    machine = Machine()
                                    machine.layer = layer
                                    machine.name = machinename
                                    update_machine_conf_file(os.path.join(repodir, path), machine)
                                    machine.save()

                    dirtyrecipes = set()
                    for d in diff.iter_change_type('M'):
                        path = d.a_blob.path
                        if path.startswith(subdir_start):
                            (filepath, filename) = split_bb_file_path(path, subdir_start)
                            if filename:
                                results = layerrecipes.filter(filepath=filepath).filter(filename=filename)[:1]
                                if results:
                                    recipe = results[0]
                                    update_recipe_file(config_data_copy, os.path.join(layerdir, filepath), recipe, layerdir_start, repodir)
                                    recipe.save()
                                    updatedrecipes.add(recipe)
                            else:
                                machinename = check_machine_conf(path)
                                if machinename:
                                    results = layermachines.filter(name=machinename)
                                    if results:
                                        machine = results[0]
                                        update_machine_conf_file(os.path.join(repodir, path), machine)
                                        machine.save()
                            deps = RecipeFileDependency.objects.filter(layer=layer).filter(path=path)
                            for dep in deps:
                                dirtyrecipes.add(dep.recipe)

                    dirtyrecipes -= updatedrecipes
                    for recipe in dirtyrecipes:
                        update_recipe_file(config_data_copy, os.path.join(layerdir, recipe.filepath), recipe, layerdir_start, repodir)
                else:
                    # Collect recipe data from scratch
                    layerrecipes.delete()
                    layermachines.delete()
                    for root, dirs, files in os.walk(layerdir):
                        for f in files:
                            if fnmatch.fnmatch(f, "*.bb"):
                                recipe = Recipe()
                                recipe.layer = layer
                                recipe.filename = f
                                recipe.filepath = os.path.relpath(root, layerdir)
                                update_recipe_file(config_data_copy, root, recipe, layerdir_start, repodir)
                                recipe.save()
                            else:
                                fullpath = os.path.join(root, f)
                                machinename = check_machine_conf(fullpath)
                                if machinename:
                                    machine = Machine()
                                    machine.layer = layer
                                    machine.name = machinename
                                    update_machine_conf_file(fullpath, machine)
                                    machine.save()

                # Save repo info
                layer.vcs_last_rev = topcommit.hexsha
                layer.vcs_last_commit = datetime.fromtimestamp(topcommit.committed_date)
            else:
                logger.info("Layer %s is already up-to-date" % layer.name)

            layer.vcs_last_fetch = datetime.now()
            layer.save()

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

    sys.exit(0)


if __name__ == "__main__":
    main()
