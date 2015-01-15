#!/usr/bin/env python

# Will create the layer and branch required by layerindex
#
# Copyright (C) 2014 Intel Corporation
# Author: Anibal Limon <anibal.limon@linux.intel.com>
# Contributor: Marius Avram <marius.avram@intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path

import utils
import recipeparse
import settings

from layerindex.models import LayerItem, Branch, LayerBranch, Recipe

from recipe_maintainer import update_recipe_maintainers
from recipe_distro import update_recipe_distros
from recipe_upgrade import update_recipe_upgrades
from recipe_upstream import update_recipe_upstream

class RrsUpdater:
    def __init__(self, fetchdir, options, layerquery, fetchedrepos,
            failedrepos, logger):
        self._fetchdir = fetchdir
        self._options = options
        self._logger = logger 
        self._layerquery = layerquery

        self._run_all = (not options.recipe_maintainers and
                        not options.recipe_distros and
                        not options.recipe_upgrades and
                        not options.recipe_upstream)

        self._filter_recipes()

    """ 
        Update the data needed by Recipe reporting system
    """
    def run(self, tinfoil):
        if self._run_all or self._options.recipe_distros:
            from oe import distro_check
            self._logger.info("Downloading distro's package information")
            distro_check.create_distro_packages_list(self._fetchdir)
            pkglst_dir = os.path.join(self._fetchdir, "package_lists")

        for layer in self._layerquery:
            (layerbranch, repodir, layerdir, config_data) = \
                self._get_config_data(layer, self._fetchdir, tinfoil)

            envdata = self._get_recipes_envdata(layerbranch, layerdir,
                    config_data, self._options)

            if self._run_all:
                self._logger.info("Updating recipe maintainers")
                update_recipe_maintainers(envdata, self._logger)
                self._logger.info("Updating recipe distros")
                update_recipe_distros(envdata, layerbranch, pkglst_dir,
                                        self._logger)
                self._logger.info("Updating recipe upgrades")
                update_recipe_upgrades(layerbranch, repodir, layerdir,
                        config_data, self._logger)
                self._logger.info("Updating recipe upstream")
                update_recipe_upstream(envdata, self._logger)
            else:
                run_maintainer = False

                if self._options.recipe_maintainers:
                    self._logger.info("Updating recipe maintainers")
                    update_recipe_maintainers(envdata, self._logger)
                    run_maintainer = True

                if self._options.recipe_distros:
                    self._logger.info("Updating recipe distros")
                    update_recipe_distros(envdata, layerbranch, pkglst_dir,
                                            self._logger)

                if self._options.recipe_upgrades:
                    self._logger.info("Updating recipe upgrades")
                    update_recipe_upgrades(layerbranch, repodir, layerdir,
                            config_data, self._logger) 

                if self._options.recipe_upstream:
                    # recipe upstream depends on recipe maintainers
                    if not run_maintainer:
                        self._logger.info("Updating recipe maintainers")
                        update_recipe_maintainers(envdata, self._logger)

                    self._logger.info("Updating recipe upstream")
                    update_recipe_upstream(envdata, self._logger)
    
    """
        Remove native and old recipes,
        Native recipes are unuseful because have target recipe.
        Older recipes means that if exist more than one version of recipe only
        take the last one.
    """
    def _filter_recipes(self):
        self._remove_native_cross_initial_recipes()
        for recipe in Recipe.objects.all():
            self._remove_older_recipes(recipe)
    
    def _remove_native_cross_initial_recipes(self):
        for recipe in Recipe.objects.all():
            if (recipe.pn.find('-native') != -1 or
                    recipe.pn.find('nativesdk-') != -1 or
                    recipe.pn.find('-cross') != -1 or
                    recipe.pn.find('-initial') != -1):
                    recipe.delete()
                    self._logger.debug('_remove_native_recipes: %s delete' % (recipe.pn))
    
    def _remove_older_recipes(self, recipe):
        # get recipes with the same pn
        recipes = Recipe.objects.filter(pn__iexact = recipe.pn)

        if recipes.count() == 1:
            return

        if 'git' in recipe.pv:
            recipe.delete()
        else:
            # remove recipes that have minor version
            for r in recipes:
                if r.id == recipe.id:
                    continue

                if bb.utils.vercmp_string(r.pv, recipe.pv) == -1:
                    r.delete()

    """
        Get configuration data required by tinfoil for poky layer.
    """
    def _get_config_data(self, layer, fetchdir, tinfoil):
        urldir = layer.get_fetch_dir()
        layerbranch = layer.get_layerbranch(self._options.branch)
        repodir = os.path.join(fetchdir, urldir)
        layerdir = os.path.join(repodir, layerbranch.vcs_subdir)
        config_data = recipeparse.setup_layer(tinfoil.config_data, fetchdir,
                        layerdir, layer, layerbranch)
        return (layerbranch, repodir, layerdir, config_data)

    """
        Parse all recipes. Called only once per update.
    """
    def _get_recipes_envdata(self, layerbranch, layerdir, config_data, options):
        envdata = {}

        if options.recipe:
            recipes = Recipe.objects.filter(layerbranch = layerbranch,
                    pn__exact = options.recipe)
        else:
            recipes = Recipe.objects.filter(layerbranch = layerbranch)
    
        for recipe in recipes:
            recipe_path = str(os.path.join(layerdir, recipe.full_path()))

            try:
                envdata[recipe] = bb.cache.Cache.loadDataFull(recipe_path,
                                        [], config_data)
            except Exception as e:
                self._logger.warn("%s, %s couldn't be parsed, %s"
                                    % (layerbranch, recipe, str(e)))
                continue

        return envdata
