#!/usr/bin/env python

# Import migration info from OE-Classic recipes wiki page into OE
# layer index database
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os.path

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import optparse
import re
import utils
import logging

logger = utils.logger_create('LayerIndexImport')


class DryRunRollbackException(Exception):
    pass


def read_page(site, path):
    ret = {}
    import httplib
    conn = httplib.HTTPConnection(site)
    conn.request("GET", path)
    resp = conn.getresponse()
    if resp.status in [200, 302]:
        data = resp.read()
        in_table = False
        for line in data.splitlines():
            if line.startswith('{|'):
                in_table = True
                continue
            if in_table:
                if line.startswith('|}'):
                    # We're done
                    in_table = False
                    continue
                elif line.startswith('!'):
                    pass
                elif not line.startswith('|-'):
                    if line.startswith("|| ''"):
                        continue
                    fields = line.split('||')
                    pn = fields[0].strip('|[]').split()[1]
                    comment = fields[1]
                    if comment:
                        ret[pn] = comment
    else:
        logger.error('Fetch failed: %d: %s' % (resp.status, resp.reason))
    return ret

def main():

    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    parser.add_option("-b", "--branch",
            help = "Specify branch to import into",
            action="store", dest="branch", default='oe-classic')
    parser.add_option("-l", "--layer",
            help = "Specify layer to import into",
            action="store", dest="layer", default='oe-classic')
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

    utils.setup_django()
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe
    from django.db import transaction

    logger.setLevel(options.loglevel)

    res = list(LayerItem.objects.filter(name=options.layer)[:1])
    if res:
        layer = res[0]
    else:
        logger.error('Specified layer %s does not exist in database' % options.layer)
        sys.exit(1)

    layerbranch = layer.get_layerbranch(options.branch)
    if not layerbranch:
        logger.error("Specified branch %s does not exist in database" % options.branch)
        sys.exit(1)

    recipes_ai = read_page("www.openembedded.org", "/wiki/OE-Classic_Recipes_A-I?action=raw")
    recipes_jz = read_page("www.openembedded.org", "/wiki/OE-Classic_Recipes_J-Z?action=raw")

    try:
        with transaction.atomic():
            recipes = dict(list(recipes_ai.items()) + list(recipes_jz.items()))
            for pn, comment in recipes.items():
                newpn = ''
                newlayer = ''
                status = 'U'
                comment = comment.strip(' -')
                if 'provided by' in comment:
                    res = re.match(r'[a-zA-Z- ]*provided by ([a-zA-Z0-9-]*) in ([a-zA-Z0-9-]*)(.*)', comment)
                    if res:
                        newpn = res.group(1)
                        newlayer = res.group(2)
                        comment = res.group(3)
                    if pn.endswith('-native') or pn.endswith('-cross'):
                        status = 'P'
                    else:
                        status = 'R'
                elif 'replaced by' in comment or 'renamed to' in comment or ' is in ' in comment:
                    res = re.match(r'.*replaced by ([a-zA-Z0-9-.]*) in ([a-zA-Z0-9-]*)(.*)', comment)
                    if not res:
                        res = re.match(r'.*renamed to ([a-zA-Z0-9-.]*) in ([a-zA-Z0-9-]*)(.*)', comment)
                    if not res:
                        res = re.match(r'([a-zA-Z0-9-.]*) is in ([a-zA-Z0-9-]*)(.*)', comment)
                    if res:
                        newpn = res.group(1)
                        newlayer = res.group(2)
                        comment = res.group(3)
                    status = 'R'
                elif 'obsolete' in comment or 'superseded' in comment:
                    res = re.match(r'provided by ([a-zA-Z0-9-]*) in ([a-zA-Z0-9-]*)(.*)', comment)
                    if res:
                        newpn = res.group(1)
                        newlayer = res.group(2)
                        comment = res.group(3)
                    elif comment.startswith('superseded by'):
                        comment = comment[14:]
                    elif comment.startswith('obsolete'):
                        comment = comment[9:]
                    status = 'O'
                elif 'PACKAGECONFIG' in comment:
                    res = re.match(r'[a-zA-Z ]* PACKAGECONFIG [a-zA-Z ]* to ([a-zA-Z0-9-]*) in ([a-zA-Z0-9-]*)(.*)', comment)
                    if res:
                        newpn = res.group(1)
                        newlayer = res.group(2)
                        comment = res.group(3)
                    status = 'C'

                if newlayer:
                    if newlayer.lower() == 'oe-core':
                        newlayer = 'openembedded-core'

                # Remove all links from comments because they'll be picked up as categories
                comment = re.sub(r'\[(http[^[]*)\]', r'\1', comment)
                # Split out categories
                categories = re.findall(r'\[([^]]*)\]', comment)
                for cat in categories:
                    comment = comment.replace('[%s]' % cat, '')
                if '(GPE)' in comment or pn.startswith('gpe'):
                    categories.append('GPE')
                    comment = comment.replace('(GPE)', '')

                comment = comment.strip('- ')

                logger.debug("%s|%s|%s|%s|%s|%s" % (pn, status, newpn, newlayer, categories, comment))

                recipequery = ClassicRecipe.objects.filter(layerbranch=layerbranch).filter(pn=pn).filter(deleted=False)
                if recipequery:
                    for recipe in recipequery:
                        recipe.cover_layerbranch = None
                        if newlayer:
                            res = list(LayerItem.objects.filter(name=newlayer)[:1])
                            if res:
                                newlayeritem = res[0]
                                recipe.cover_layerbranch = newlayeritem.get_layerbranch('master')
                            else:
                                logger.info('Replacement layer "%s" for %s could not be found' % (newlayer, pn))
                        recipe.cover_pn = newpn
                        recipe.cover_status = status
                        recipe.cover_verified = True
                        recipe.cover_comment = comment
                        recipe.classic_category = " ".join(categories)
                        recipe.save()
                else:
                    logger.info('No OE-Classic recipe with name "%s" count be found' % pn)
                    sys.exit(1)

            if options.dryrun:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
