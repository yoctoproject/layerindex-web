# Utility functions for parsing recipes using bitbake within layerindex-web
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import os.path
import utils
import tempfile
import re
import fnmatch

class RecipeParseError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg



def init_parser(settings, branch, bitbakepath, enable_tracking=False, nocheckout=False, classic=False, logger=None):
    if not (nocheckout or classic):
        # Check out the branch of BitBake appropriate for this branch and clean out any stale files (e.g. *.pyc)
        if re.match('[0-9a-f]{40}', branch.bitbake_branch):
            # SHA1 hash
            bitbake_ref = branch.bitbake_branch
        else:
            # Branch name
            bitbake_ref = 'origin/%s' % branch.bitbake_branch
        utils.checkout_repo(bitbakepath, bitbake_ref, logger=logger)

    # Skip sanity checks
    os.environ['BB_ENV_EXTRAWHITE'] = 'DISABLE_SANITY_CHECKS'
    os.environ['DISABLE_SANITY_CHECKS'] = '1'

    fetchdir = settings.LAYER_FETCH_DIR

    if not classic:
        # Ensure we have OE-Core set up to get some base configuration
        core_layer = utils.get_layer(settings.CORE_LAYER_NAME)
        if not core_layer:
            raise RecipeParseError("Unable to find core layer %s in database; create this layer or set the CORE_LAYER_NAME setting to point to the core layer" % settings.CORE_LAYER_NAME)
        core_layerbranch = core_layer.get_layerbranch(branch.name)
        core_branchname = branch.name
        if core_layerbranch:
            core_subdir = core_layerbranch.vcs_subdir
            if core_layerbranch.actual_branch:
                core_branchname = core_layerbranch.actual_branch
        else:
            core_subdir = 'meta'
        core_urldir = core_layer.get_fetch_dir()
        core_repodir = os.path.join(fetchdir, core_urldir)
        core_layerdir = os.path.join(core_repodir, core_subdir)
        if not nocheckout:
            utils.checkout_repo(core_repodir, "origin/%s" % core_branchname, logger=logger)
        if not os.path.exists(os.path.join(core_layerdir, 'conf/bitbake.conf')):
            raise RecipeParseError("conf/bitbake.conf not found in core layer %s - is subdirectory set correctly?" % core_layer.name)
        # The directory above where this script exists should contain our conf/layer.conf,
        # so add it to BBPATH along with the core layer directory
        confparentdir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        os.environ['BBPATH'] = str("%s:%s" % (confparentdir, core_layerdir))

    # Change into a temporary directory so we don't write the cache and other files to the current dir
    if not os.path.exists(settings.TEMP_BASE_DIR):
        os.makedirs(settings.TEMP_BASE_DIR)
    tempdir = tempfile.mkdtemp(dir=settings.TEMP_BASE_DIR)
    saved_cwd = os.getcwd()
    os.chdir(tempdir)
    # We need to create a dummy bblayers.conf to avoid bitbake-cookerdaemon.log being created in <oecore>/meta/
    # (see findTopdir() in bitbake/lib/bb/cookerdata.py)
    os.mkdir(os.path.join(tempdir, 'conf'))
    with open(os.path.join(tempdir, 'conf', 'bblayers.conf'), 'w') as f:
        pass

    if logger:
        tinfoil = utils.setup_tinfoil(bitbakepath, enable_tracking, loglevel=logger.getEffectiveLevel())
    else:
        tinfoil = utils.setup_tinfoil(bitbakepath, enable_tracking)

    os.chdir(saved_cwd)

    # Ensure TMPDIR exists (or insane.bbclass will blow up trying to write to the QA log)
    oe_tmpdir = tinfoil.config_data.getVar('TMPDIR', True)
    if not os.path.exists(oe_tmpdir):
        os.makedirs(oe_tmpdir)

    # Ensure BBFILES as an initial value so that the old mode of BBFILES := "${BBFILES} ..." works
    if not tinfoil.config_data.getVar('BBFILES', False):
        tinfoil.config_data.setVar('BBFILES', '')

    return (tinfoil, tempdir)

def setup_layer(config_data, fetchdir, layerdir, layer, layerbranch, logger):
    # Parse layer.conf files for this layer and its dependencies
    # This is necessary not just because BBPATH needs to be set in order
    # for include/require/inherit to work outside of the current directory
    # or across layers, but also because custom variable values might be
    # set in layer.conf.
    config_data_copy = bb.data.createCopy(config_data)
    utils.parse_layer_conf(layerdir, config_data_copy)
    for dep in layerbranch.dependencies_set.all():
        depurldir = dep.dependency.get_fetch_dir()
        deprepodir = os.path.join(fetchdir, depurldir)
        deplayerbranch = dep.dependency.get_layerbranch(layerbranch.branch.name)
        if not deplayerbranch:
            if dep.required:
                raise RecipeParseError('Dependency %s of layer %s does not have branch record for branch %s' % (dep.dependency.name, layer.name, layerbranch.branch.name))
            else:
                logger.warning('Recommends %s of layer %s does not have branch record for branch %s - ignoring' % (dep.dependency.name, layer.name, layerbranch.branch.name))
                continue
        deplayerdir = os.path.join(deprepodir, deplayerbranch.vcs_subdir)
        utils.parse_layer_conf(deplayerdir, config_data_copy)
    config_data_copy.delVar('LAYERDIR')
    return config_data_copy

machine_conf_re = re.compile(r'conf/machine/([^/.]*).conf$')
distro_conf_re = re.compile(r'conf/distro/([^/.]*).conf$')
bbclass_re = re.compile(r'classes/([^/.]*).bbclass$')
def detect_file_type(path, subdir_start):
    typename = None
    if fnmatch.fnmatch(path, "*.bb"):
        typename = 'recipe'
    elif fnmatch.fnmatch(path, "*.bbappend"):
        typename = 'bbappend'
    elif fnmatch.fnmatch(path, "*.inc"):
        typename = 'incfile'
    else:
        # Check if it's a machine conf file
        subpath = path[len(subdir_start):]
        res = machine_conf_re.match(subpath)
        if res:
            typename = 'machine'
            return (typename, None, res.group(1))
        res = bbclass_re.match(subpath)
        if res:
            typename = 'bbclass'
            return (typename, None, res.group(1))
        res = distro_conf_re.match(subpath)
        if res:
            typename = 'distro'
            return (typename, None, res.group(1))

    if typename in ['recipe', 'bbappend', 'incfile']:
        if subdir_start:
            filepath = os.path.relpath(os.path.dirname(path), subdir_start)
        else:
            filepath = os.path.dirname(path)
        return (typename, filepath, os.path.basename(path))

    return (None, None, None)


def handle_recipe_depends(recipe, depends, packageconfig_opts):
    from layerindex.models import StaticBuildDep, PackageConfig, DynamicBuildDep

    # Handle static build dependencies for this recipe
    for dep in depends.split():
        static_build_dependency, created = StaticBuildDep.objects.get_or_create(name=dep)
        if created:
            static_build_dependency.save()
        static_build_dependency.recipes.add(recipe)

    # Handle the PACKAGECONFIG variables for this recipe
    PackageConfig.objects.filter(recipe=recipe).delete()
    for key, value in packageconfig_opts.items():
        if key == "doc":
            continue
        package_config = PackageConfig()
        package_config.feature = key
        package_config.recipe = recipe
        package_config_vals = value.split(",")
        try:
            package_config.build_deps = package_config_vals[2]
        except IndexError:
            pass
        try:
            package_config.with_option = package_config_vals[0]
        except IndexError:
            pass
        try:
            package_config.without_option = package_config_vals[1]
        except IndexError:
            pass
        package_config.save()
        # Handle the dynamic dependencies for the PACKAGECONFIG variable
        if package_config.build_deps:
            for dep in package_config.build_deps.split():
                dynamic_build_dependency, created = DynamicBuildDep.objects.get_or_create(name=dep)
                if created:
                    dynamic_build_dependency.save()
                dynamic_build_dependency.package_configs.add(package_config)
                dynamic_build_dependency.recipes.add(recipe)
    
