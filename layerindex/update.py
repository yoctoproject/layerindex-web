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


def split_path(subdir_start, recipe_path):
    if recipe_path.startswith(subdir_start) and fnmatch.fnmatch(recipe_path, "*.bb"):
        if subdir_start:
            filepath = os.path.relpath(os.path.dirname(recipe_path), subdir_start)
        else:
            filepath = os.path.dirname(recipe_path)
        return (filepath, os.path.basename(recipe_path))
    return (None, None)


def update_recipe_file(bbhandler, path, recipe):
    fn = str(os.path.join(path, recipe.filename))
    try:
        envdata = bb.cache.Cache.loadDataFull(fn, [], bbhandler.config_data)
        envdata.setVar('SRCPV', 'X')
        recipe.pn = envdata.getVar("PN", True)
        recipe.pv = envdata.getVar("PV", True)
        recipe.summary = envdata.getVar("SUMMARY", True)
        recipe.description = envdata.getVar("DESCRIPTION", True)
        recipe.section = envdata.getVar("SECTION", True)
        recipe.license = envdata.getVar("LICENSE", True)
        recipe.homepage = envdata.getVar("HOMEPAGE", True)
    except Exception as e:
        logger.info("Unable to read %s: %s", fn, str(e))


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

    parser.add_option("-r", "--reload",
            help = "Discard existing recipe data and fetch it from scratch",
            action="store_true", dest="reload")
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
    from layerindex.models import LayerItem, Recipe
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


    # Fetch all layers
    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)
    fetchedrepos = []
    failedrepos = []
    for layer in LayerItem.objects.filter(status='P'):
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
            # Handle multiple layers in a single repo
            urldir = sanitise_path(layer.vcs_url)
            repodir = os.path.join(fetchdir, urldir)
            if layer.vcs_url in failedrepos:
                logger.info("Skipping remote repository %s as it has already failed" % layer.vcs_url)
                transaction.rollback()
                continue
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
                    transaction.rollback()
                    continue
                fetchedrepos.append(layer.vcs_url)

            # Collect repo info
            repo = git.Repo(repodir)
            assert repo.bare == False
            topcommit = repo.commit('master')

            layerdir = os.path.join(repodir, layer.vcs_subdir)
            layerrecipes = Recipe.objects.filter(layer=layer)
            if layer.vcs_last_rev != topcommit.hexsha or options.reload:
                logger.info("Collecting data for layer %s" % layer.name)

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

                    for d in diff.iter_change_type('D'):
                        path = d.a_blob.path
                        (filepath, filename) = split_path(subdir_start, path)
                        if filename:
                            layerrecipes.filter(filepath=filepath).filter(filename=filename).delete()

                    for d in diff.iter_change_type('A'):
                        path = d.b_blob.path
                        (filepath, filename) = split_path(subdir_start, path)
                        if filename:
                            recipe = Recipe()
                            recipe.layer = layer
                            recipe.filename = filename
                            recipe.filepath = filepath
                            update_recipe_file(tinfoil, os.path.join(layerdir, filepath), recipe)
                            recipe.save()

                    for d in diff.iter_change_type('M'):
                        path = d.a_blob.path
                        (filepath, filename) = split_path(subdir_start, path)
                        if filename:
                            results = layerrecipes.filter(filepath=filepath).filter(filename=filename)[:1]
                            if results:
                                recipe = results[0]
                                update_recipe_file(tinfoil, os.path.join(layerdir, filepath), recipe)
                                recipe.save()
                else:
                    # Collect recipe data from scratch
                    layerrecipes.delete()
                    for root, dirs, files in os.walk(layerdir):
                        for f in files:
                            if fnmatch.fnmatch(f, "*.bb"):
                                recipe = Recipe()
                                recipe.layer = layer
                                recipe.filename = f
                                recipe.filepath = os.path.relpath(root, layerdir)
                                update_recipe_file(tinfoil, root, recipe)
                                recipe.save()

                # Save repo info
                layer.vcs_last_rev = topcommit.hexsha
                layer.vcs_last_commit = datetime.fromtimestamp(topcommit.committed_date)
            else:
                logger.info("Layer %s is already up-to-date" % layer.name)

            layer.vcs_last_fetch = datetime.now()
            layer.save()

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
