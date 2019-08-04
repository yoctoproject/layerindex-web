#!/usr/bin/env python3

# Import layers from another layer index instance
#
# Copyright (C) 2018 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import optparse
import re
import glob
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
    valid_layer_name = re.compile('[-\w]+$')

    parser = optparse.OptionParser(
        usage = """
    %prog [options] <url>""")

    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")

    options, args = parser.parse_args(sys.argv)

    if len(args) < 2:
        print("Please specify URL of the layer index")
        sys.exit(1)

    layerindex_url = args[1]

    utils.setup_django()
    import settings
    from layerindex.models import Branch, LayerItem, LayerBranch, LayerDependency, LayerMaintainer, LayerNote
    from django.db import transaction

    logger.setLevel(options.loglevel)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)

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

    logger.debug('Getting branches')

    # Get branches (we assume the ones we want are already there, so skip any that aren't)
    rq = urllib.request.Request(branches_url)
    data = urllib.request.urlopen(rq).read()
    jsdata = json.loads(data.decode('utf-8'))
    branch_idmap = {}
    for branchjs in jsdata:
        res = Branch.objects.filter(name=branchjs['name'])
        if res:
            branch = res.first()
            branch_idmap[branchjs['id']] = branch

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
            jsdata = json.loads(data.decode('utf-8'))

            layerbranch_idmap = {}
            exclude_fields = ['id', 'layer', 'branch', 'vcs_last_fetch', 'vcs_last_rev', 'vcs_last_commit', 'yp_compatible_version', 'updated']
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

            if options.dryrun:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
