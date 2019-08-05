#!/usr/bin/env python3

# Import layers from another layer index instance
#
# Copyright (C) 2018 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import argparse
import re
import logging
import subprocess
import urllib.request
import json
import datetime
from django.utils import timezone

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import utils
from layerconfparse import LayerConfParse

class DryRunRollbackException(Exception):
    pass

logger = utils.logger_create('LayerIndexImport')


iso8601_date_re = re.compile('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}')
def datetime_hook(jsdict):
    for key, value in jsdict.items():
        if isinstance(value, str) and iso8601_date_re.match(value):
            jsdict[key] = timezone.make_naive(datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z"))
    return jsdict



def main():
    parser = argparse.ArgumentParser(description="Layer index import utility. Imports layer information from another layer index instance using the REST API. WARNING: this will overwrite data in your database, use with caution!")
    parser.add_argument('url', help='Layer index URL to fetch from')
    parser.add_argument('-b', '--branch', action='store', help='Restrict to import a specific branch only (separate multiple branches with commas)')
    parser.add_argument('-l', '--layer', action='store', help='Restrict to import a specific layer only (regular expressions allowed)')
    parser.add_argument('-n', '--dry-run', action='store_true', help="Don't write any data back to the database")
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Hide all output except error messages')

    args = parser.parse_args()

    if args.debug:
        loglevel = logging.DEBUG
    elif args.quiet:
        loglevel = logging.WARNING
    else:
        loglevel = logging.INFO

    utils.setup_django()
    import settings
    from layerindex.models import Branch, LayerItem, LayerBranch, LayerDependency, LayerMaintainer, LayerNote, Recipe, Source, Patch, PackageConfig, StaticBuildDep, DynamicBuildDep, RecipeFileDependency, Machine, Distro, BBClass, BBAppend, IncFile
    from django.db import transaction

    logger.setLevel(loglevel)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)

    layerindex_url = args.url
    if not layerindex_url.endswith('/'):
        layerindex_url += '/'
    if not '/layerindex/api/' in layerindex_url:
        layerindex_url += 'layerindex/api/'

    rq = urllib.request.Request(layerindex_url)
    data = urllib.request.urlopen(rq).read()
    jsdata = json.loads(data.decode('utf-8'))

    branches_url = jsdata['branches']
    layers_url = jsdata['layerItems']
    layerdeps_url = jsdata['layerDependencies']
    layerbranches_url = jsdata['layerBranches']
    layermaintainers_url = jsdata.get('layerMaintainers', None)
    layernotes_url = jsdata.get('layerNotes', None)
    recipes_url = jsdata.get('recipes', None)
    machines_url = jsdata.get('machines', None)
    distros_url = jsdata.get('distros', None)
    classes_url = jsdata.get('classes', None)
    appends_url = jsdata.get('appends', None)
    incfiles_url = jsdata.get('incFiles', None)

    logger.debug('Getting branches')

    # Get branches (we assume the ones we want are already there, so skip any that aren't)
    rq = urllib.request.Request(branches_url)
    data = urllib.request.urlopen(rq).read()
    jsdata = json.loads(data.decode('utf-8'))
    branch_idmap = {}
    filter_branches = []
    if args.branch:
        for branch in args.branch.split(','):
            if not Branch.objects.filter(name=branch).exists():
                logger.error('"%s" is not a valid branch in this database (branches must be created manually first)' % branch)
                sys.exit(1)
            filter_branches.append(branch)
    for branchjs in jsdata:
        if filter_branches and branchjs['name'] not in filter_branches:
            logger.debug('Skipping branch %s, not in specified branch list' % branchjs['name'])
            continue
        res = Branch.objects.filter(name=branchjs['name'])
        if res:
            branch = res.first()
            branch_idmap[branchjs['id']] = branch
        else:
            logger.debug('Skipping branch %s, not in database' % branchjs['name'])

    if args.layer:
        layer_re = re.compile('^' + args.layer + '$')
    else:
        layer_re = None

    try:
        with transaction.atomic():
            # Get layers
            logger.debug('Importing layers')
            rq = urllib.request.Request(layers_url)
            data = urllib.request.urlopen(rq).read()
            jsdata = json.loads(data.decode('utf-8'), object_hook=datetime_hook)

            layer_idmap = {}
            exclude_fields = ['id', 'updated']
            for layerjs in jsdata:
                if layer_re and not layer_re.match(layerjs['name']):
                    logger.debug('Skipping layer %s, does not match layer restriction' % layerjs['name'])
                    continue

                layeritem = LayerItem.objects.filter(name=layerjs['name']).first()
                if layeritem:
                    # Already have this layer
                    if layerjs['updated'] <= layeritem.updated:
                        logger.debug('Skipping layer %s, already up-to-date' % layerjs['name'])
                        layer_idmap[layerjs['id']] = layeritem
                        continue
                    else:
                        logger.debug('Updating layer %s' % layerjs['name'])
                else:
                    logger.debug('Adding layer %s' % layerjs['name'])
                    layeritem = LayerItem()
                for key, value in layerjs.items():
                    if key in exclude_fields:
                        continue
                    setattr(layeritem, key, value)
                layeritem.save()
                layer_idmap[layerjs['id']] = layeritem

            # Get layer branches
            logger.debug('Importing layer branches')
            rq = urllib.request.Request(layerbranches_url)
            data = urllib.request.urlopen(rq).read()
            jsdata = json.loads(data.decode('utf-8'), object_hook=datetime_hook)

            layerbranch_idmap = {}

            def import_child_items(parentobj, objclass, childlist=None, url=None, parent_orig_id=None, parentfield=None, exclude_fields=None, key_fields=None, custom_fields=None, custom_field_cb=None):
                logger.debug('Importing %s for %s' % (objclass._meta.verbose_name_plural, parentobj))

                if parentfield is None:
                    parentfield = parentobj.__class__.__name__.lower()

                if exclude_fields is None:
                    exclude = ['id', parentfield]
                else:
                    exclude = exclude_fields[:]
                if custom_fields is not None:
                    exclude += custom_fields
                if key_fields is None:
                    keys = None
                else:
                    # The parent field always needs to be part of the keys
                    keys = key_fields + [parentfield]

                if url:
                    if parent_orig_id is None:
                        raise Exception('import_child_items: if url is specified then parent_orig_id must also be specified')
                    rq = urllib.request.Request(url + '?filter=%s:%s' % (parentfield, parent_orig_id))
                    data = urllib.request.urlopen(rq).read()
                    childjslist = json.loads(data.decode('utf-8'))
                elif childlist is not None:
                    childjslist = childlist
                else:
                    raise Exception('import_child_items: either url or childlist must be specified')

                manager = getattr(parentobj, objclass.__name__.lower() + '_set')
                existing_ids = list(manager.values_list('id', flat=True))
                updated_ids = []
                for childjs in childjslist:
                    vals = {}
                    for key, value in childjs.items():
                        if key in exclude:
                            continue
                        vals[key] = value
                    vals[parentfield] = parentobj

                    if keys:
                        keyvals = {k: vals[k] for k in keys}
                    else:
                        keyvals = vals

                    # In the case of multiple records with the same keys (e.g. multiple recipes with same pn),
                    # we need to skip ones we've already touched
                    obj = None
                    created = False
                    for entry in manager.filter(**keyvals):
                        if entry.id not in updated_ids:
                            obj = entry
                            break
                    else:
                        created = True
                        obj = objclass(**keyvals)

                    for key, value in vals.items():
                        setattr(obj, key, value)
                    # Need to have saved before calling custom_field_cb since the function might be adding child objects
                    obj.save()
                    updated_ids.append(obj.id)
                    if custom_field_cb is not None:
                        custom_field_cb(obj, childjs)
                    if not created:
                        if obj.id in existing_ids:
                            existing_ids.remove(obj.id)
                for idv in existing_ids:
                    objclass.objects.filter(id=idv).delete()

            def package_config_field_handler(package_config, pjsdata):
                for dep in pjsdata['builddeps']:
                    dynamic_build_dependency, created = DynamicBuildDep.objects.get_or_create(name=dep)
                    if created:
                        dynamic_build_dependency.save()
                    dynamic_build_dependency.package_configs.add(package_config)
                    dynamic_build_dependency.recipes.add(package_config.recipe)

            def recipe_field_handler(recipe, recipejs):
                sources = recipejs.get('sources', [])
                import_child_items(recipe, Source, childlist=sources, key_fields=['url'])
                patches = recipejs.get('patches', [])
                import_child_items(recipe, Patch, childlist=patches, key_fields=['path'])
                existing_deps = list(recipe.staticbuilddep_set.values_list('name', flat=True))
                for dep in recipejs['staticbuilddeps']:
                    depobj, created = StaticBuildDep.objects.get_or_create(name=dep)
                    if created:
                        depobj.save()
                    elif dep in existing_deps:
                        existing_deps.remove(dep)
                    depobj.recipes.add(recipe)
                for existing_dep in existing_deps:
                    recipe.staticbuilddep_set.filter(name=existing_dep).recipes.remove(recipe)
                package_configs = recipejs.get('package_configs', [])
                import_child_items(recipe, PackageConfig, childlist=package_configs, custom_fields=['builddeps'], custom_field_cb=package_config_field_handler, key_fields=['feature'])

                # RecipeFileDependency objects need to be handled specially (since they link to a separate LayerBranch)
                existing_filedeps = list(recipe.recipefiledependency_set.values_list('id', flat=True))
                filedeps = recipejs.get('filedeps', [])
                for filedep in filedeps:
                    target_layerbranch = layerbranch_idmap.get(filedep['layerbranch'], None)
                    if target_layerbranch is None:
                        logger.debug('Skipping recipe file dependency on layerbranch %s, branch not imported' % filedep['layerbranch'])
                        continue
                    depobj, created = RecipeFileDependency.objects.get_or_create(recipe=recipe, layerbranch=target_layerbranch, path=filedep['path'])
                    if created:
                        depobj.save()
                    elif depobj.id in existing_filedeps:
                        existing_filedeps.remove(depobj.id)
                for idv in existing_filedeps:
                    RecipeFileDependency.objects.filter(id=idv).delete()

            # Get list of layerbranches that currently exist, so we can delete any that
            # we don't find in the remote layer index (assuming they are on branches
            # that *do* exist in the remote index and are in the list specified by
            # -b/--branch, if any)
            existing_layerbranches = list(LayerBranch.objects.filter(branch__in=branch_idmap.values()).values_list('id', flat=True))

            exclude_fields = ['id', 'layer', 'branch', 'yp_compatible_version', 'updated']
            for layerbranchjs in jsdata:
                branch = branch_idmap.get(layerbranchjs['branch'], None)
                if not branch:
                    # We don't have this branch, skip it
                    logger.debug('Skipping layerbranch %s, branch not imported' % layerbranchjs['id'])
                    continue
                layer = layer_idmap.get(layerbranchjs['layer'], None)
                if not layer:
                    # We didn't import this layer, skip it
                    logger.debug('Skipping layerbranch %s, layer not imported' % layerbranchjs['id'])
                    continue
                layerbranch = LayerBranch.objects.filter(layer=layer).filter(branch=branch).first()
                if layerbranch:
                    # The layerbranch already exists (this will occur for layers
                    # that already existed, since we need to have those in layer_idmap
                    # to be able to import layer dependencies)
                    existing_layerbranches.remove(layerbranch.id)
                    if layerbranchjs['updated'] <= layerbranch.updated:
                        logger.debug('Skipping layerbranch %s, already up-to-date' % layerbranchjs['id'])
                        layerbranch_idmap[layerbranchjs['id']] = layerbranch
                        continue
                else:
                    layerbranch = LayerBranch()
                    layerbranch.branch = branch
                    layerbranch.layer = layer

                for key, value in layerbranchjs.items():
                    if key in exclude_fields:
                        continue
                    setattr(layerbranch, key, value)
                layerbranch.save()
                layerbranch_idmap[layerbranchjs['id']] = layerbranch

                if recipes_url:
                    import_child_items(layerbranch,
                                       Recipe,
                                       url=recipes_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       custom_fields=['sources', 'patches', 'package_configs'],
                                       custom_field_cb=recipe_field_handler,
                                       key_fields=['pn'])

                if machines_url:
                    import_child_items(layerbranch,
                                       Machine,
                                       url=machines_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       key_fields=['name'])

                if distros_url:
                    import_child_items(layerbranch,
                                       Distro,
                                       url=distros_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       key_fields=['name'])

                # The models below don't have an "updated" field at present, but it does
                # no harm to leave it as excluded in case it does get added in the future

                if classes_url:
                    import_child_items(layerbranch,
                                       BBClass,
                                       url=classes_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       key_fields=['name'])

                if appends_url:
                    import_child_items(layerbranch,
                                       BBAppend,
                                       url=appends_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       key_fields=['filename'])

                if incfiles_url:
                    import_child_items(layerbranch,
                                       IncFile,
                                       url=incfiles_url,
                                       parent_orig_id=layerbranchjs['id'],
                                       exclude_fields=['id', 'layerbranch', 'updated'],
                                       key_fields=['path'])

            for idv in existing_layerbranches:
                layerbranch = LayerBranch.objects.get(id=idv)
                if layer_re is None or layer_re.match(layerbranch.layer.name):
                    logger.debug('Deleting layerbranch %s' % layerbranch)
                    layerbranch.delete()

            # Get layer dependencies
            logger.debug('Importing layer dependencies')
            rq = urllib.request.Request(layerdeps_url)
            data = urllib.request.urlopen(rq).read()
            jsdata = json.loads(data.decode('utf-8'))

            exclude_fields = ['id', 'layerbranch', 'dependency', 'updated']
            existing_deps = []
            for layerbranch in layerbranch_idmap.values():
                existing_deps += list(LayerDependency.objects.filter(layerbranch=layerbranch).values_list('id', flat=True))
            for layerdepjs in jsdata:
                layerbranch = layerbranch_idmap.get(layerdepjs['layerbranch'], None)
                if not layerbranch:
                    # We didn't import this layerbranch, skip it
                    continue
                dependency = layer_idmap.get(layerdepjs['dependency'], None)
                if not dependency:
                    # We didn't import the dependency, skip it
                    continue

                layerdep, created = LayerDependency.objects.get_or_create(layerbranch=layerbranch, dependency=dependency)
                if not created and layerdep.id in existing_deps:
                    existing_deps.remove(layerdep.id)
                for key, value in layerdepjs.items():
                    if key in exclude_fields:
                        continue
                    setattr(layerdep, key, value)
                layerdep.save()
            for idv in existing_deps:
                LayerDependency.objects.filter(id=idv).delete()

            def import_items(desc, url, exclude_fields, objclass, idmap, parentfield):
                logger.debug('Importing %s' % desc)
                rq = urllib.request.Request(url)
                data = urllib.request.urlopen(rq).read()
                jsdata = json.loads(data.decode('utf-8'))

                existing_ids = []
                for parentobj in idmap.values():
                    existing_ids += list(objclass.objects.values_list('id', flat=True))

                for itemjs in jsdata:
                    parentobj = idmap.get(itemjs[parentfield], None)
                    if not parentobj:
                        # We didn't import the parent, skip it
                        continue

                    vals = {}
                    for key, value in itemjs.items():
                        if key in exclude_fields:
                            continue
                        vals[key] = value

                    vals[parentfield] = parentobj
                    manager = getattr(parentobj, objclass.__name__.lower() + '_set')
                    obj, created = manager.get_or_create(**vals)
                    for key, value in vals.items():
                        setattr(obj, key, value)
                    obj.save()

                for idv in existing_deps:
                    objclass.objects.filter(id=idv).delete()

            if layermaintainers_url:
                import_items('layer maintainers',
                            layermaintainers_url,
                            ['id', 'layerbranch'],
                            LayerMaintainer,
                            layerbranch_idmap,
                            'layerbranch')

            if layernotes_url:
                import_items('layer notes',
                            layernotes_url,
                            ['id', 'layer'],
                            LayerNote,
                            layer_idmap,
                            'layer')

            if args.dry_run:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
