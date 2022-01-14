#!/usr/bin/env python3

# Import layer index wiki page into database
#
# Copyright (C) 2013 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT


import sys
import os.path

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import optparse
import re
import utils

logger = utils.logger_create('LayerIndexImport')


class DryRunRollbackException(Exception):
    pass


def main():

    parser = optparse.OptionParser(
        usage = """
    %prog [options]""")

    options, args = parser.parse_args(sys.argv)

    utils.setup_django()
    from layerindex.models import LayerItem, LayerBranch, LayerDependency
    from django.db import transaction

    import httplib
    conn = httplib.HTTPConnection("www.openembedded.org")
    conn.request("GET", "/wiki/LayerIndex?action=raw")
    resp = conn.getresponse()
    if resp.status in [200, 302]:
        data = resp.read()
        in_table = False
        layer_type = 'M'
        nowiki_re = re.compile(r'</?nowiki>')
        link_re = re.compile(r'\[(http.*) +link\]')
        readme_re = re.compile(r';f=[a-zA-Z0-9/-]*README;')
        master_branch = utils.get_branch('master')
        core_layer = None
        with transaction.atomic():
            for line in data.splitlines():
                if line.startswith('{|'):
                    in_table = True
                    continue
                if in_table:
                    if line.startswith('|}'):
                        # We're done
                        break
                    elif line.startswith('!'):
                        section = line.split('|', 1)[1].strip("'")
                        if section.startswith('Base'):
                            layer_type = 'A'
                        elif section.startswith('Board'):
                            layer_type = 'B'
                        elif section.startswith('Software'):
                            layer_type = 'S'
                        elif section.startswith('Distribution'):
                            layer_type = 'D'
                        else:
                            layer_type = 'M'
                    elif not line.startswith('|-'):
                        if line.startswith("|| ''"):
                            continue
                        fields = line.split('||')
                        layer = LayerItem()
                        layer.name = fields[1].strip()
                        if ' ' in layer.name:
                            logger.warn('Skipping layer %s - name invalid' % layer.name)
                            continue
                        logger.info('Adding layer %s' % layer.name)
                        layer.status = 'P'
                        layer.layer_type = layer_type
                        layer.summary = fields[2].strip()
                        layer.description = layer.summary
                        if len(fields) > 6:
                            res = link_re.match(fields[6].strip())
                            if res:
                                link = res.groups(1)[0].strip()
                                if link.endswith('/README') or readme_re.search(link):
                                    link = 'README'
                                layer.usage_url = link

                        repoval = nowiki_re.sub('', fields[4]).strip()
                        layer.vcs_url = repoval
                        if repoval.startswith('git://git.openembedded.org/'):
                            reponame = re.sub('^.*/', '', repoval)
                            layer.vcs_web_url = 'http://cgit.openembedded.org/' + reponame
                            layer.vcs_web_tree_base_url = 'http://cgit.openembedded.org/' + reponame + '/tree/%path%?h=%branch%'
                            layer.vcs_web_file_base_url = 'http://cgit.openembedded.org/' + reponame + '/tree/%path%?h=%branch%'
                            layer.vcs_web_commit_url = 'http://cgit.openembedded.org/' + reponame + '/commit/?id=%hash%'
                        elif repoval.startswith('git://git.yoctoproject.org/'):
                            reponame = re.sub('^.*/', '', repoval)
                            layer.vcs_web_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame
                            layer.vcs_web_tree_base_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/tree/%path%?h=%branch%'
                            layer.vcs_web_file_base_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/tree/%path%?h=%branch%'
                            layer.vcs_web_commit_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/commit/?id=%hash%'
                        elif repoval.startswith('git://github.com/') or repoval.startswith('http://github.com/') or repoval.startswith('https://github.com/'):
                            reponame = re.sub('^.*github.com/', '', repoval)
                            reponame = re.sub('.git$', '', reponame)
                            layer.vcs_web_url = 'http://github.com/' + reponame
                            layer.vcs_web_tree_base_url = 'http://github.com/' + reponame + '/tree/%branch%/'
                            layer.vcs_web_file_base_url = 'http://github.com/' + reponame + '/blob/%branch%/'
                            layer.vcs_web_commit_url = 'http://github.com/' + reponame + '/commit/%hash%'
                        elif repoval.startswith('git://gitlab.com/') or repoval.startswith('http://gitlab.com/') or repoval.startswith('https://gitlab.com/'):
                            reponame = re.sub('^.*gitlab.com/', '', repoval)
                            reponame = re.sub('.git$', '', reponame)
                            layer.vcs_web_url = 'http://gitlab.com/' + reponame
                            layer.vcs_web_tree_base_url = 'http://gitlab.com/' + reponame + '/tree/%branch%/'
                            layer.vcs_web_file_base_url = 'http://gitlab.com/' + reponame + '/blob/%branch%/'
                            layer.vcs_web_commit_url = 'http://gitlab.com/' + reponame + '/commit/%hash%'
                        elif repoval.startswith('git://bitbucket.org/') or repoval.startswith('http://bitbucket.org/') or repoval.startswith('https://bitbucket.org/'):
                            reponame = re.sub('^.*bitbucket.org/', '', repoval)
                            reponame = re.sub('.git$', '', reponame)
                            layer.vcs_web_url = 'http://bitbucket.org/' + reponame
                            layer.vcs_web_tree_base_url = 'http://bitbucket.org/' + reponame + '/src/%branch%/%path%?at=%branch%'
                            layer.vcs_web_file_base_url = 'http://bitbucket.org/' + reponame + '/src/%branch%/%path%?at=%branch%'
                            layer.vcs_web_commit_url = 'http://bitbucket.org/' + reponame + '/commits/%hash%'
                        elif '.git' in repoval:
                            res = link_re.match(fields[5].strip())
                            layer.vcs_web_url = res.groups(1)[0]
                            layer.vcs_web_tree_base_url = re.sub(r'\.git.*', '.git;a=tree;f=%path%;hb=%branch%', layer.vcs_web_url)
                            layer.vcs_web_file_base_url = re.sub(r'\.git.*', '.git;a=blob;f=%path%;hb=%branch%', layer.vcs_web_url)
                            layer.vcs_web_file_base_url = re.sub(r'\.git.*', '.git;a=commit;h=%hash%', layer.vcs_web_url)

                        layer.save()
                        layerbranch = LayerBranch()
                        layerbranch.layer = layer
                        layerbranch.branch = master_branch
                        layerbranch.vcs_subdir = fields[3].strip()
                        layerbranch.save()
                        if layer.name != 'openembedded-core':
                            if not core_layer:
                                core_layer = utils.get_layer('openembedded-core')
                            if core_layer:
                                layerdep = LayerDependency()
                                layerdep.layerbranch = layerbranch
                                layerdep.dependency = core_layer
                                layerdep.save()
    else:
        logger.error('Fetch failed: %d: %s' % (resp.status, resp.reason))

    sys.exit(0)


if __name__ == "__main__":
    main()
