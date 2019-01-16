#!/usr/bin/env python3

# Import a layer into the database
#
# Copyright (C) 2016 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os.path

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import optparse
import re
import glob
import utils
import logging
import subprocess
from layerconfparse import LayerConfParse

class DryRunRollbackException(Exception):
    pass

logger = utils.logger_create('LayerIndexImport')

link_re = re.compile(r'\[(http.*) +link\]')

def set_vcs_fields(layer, repoval):
    layer.vcs_url = repoval
    if repoval.startswith('git://git.openembedded.org/'):
        reponame = re.sub('^.*/', '', repoval)
        layer.vcs_web_url = 'http://cgit.openembedded.org/' + reponame
        layer.vcs_web_tree_base_url = 'http://cgit.openembedded.org/' + reponame + '/tree/%path%?h=%branch%'
        layer.vcs_web_file_base_url = 'http://cgit.openembedded.org/' + reponame + '/tree/%path%?h=%branch%'
        layer.vcs_web_commit_url = 'http://cgit.openembedded.org/' + reponame + '/commit/?id=%hash%'
    elif 'git.yoctoproject.org/' in repoval:
        reponame = re.sub('^.*/', '', repoval)
        layer.vcs_web_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame
        layer.vcs_web_tree_base_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/tree/%path%?h=%branch%'
        layer.vcs_web_file_base_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/tree/%path%?h=%branch%'
        layer.vcs_web_commit_url = 'http://git.yoctoproject.org/cgit/cgit.cgi/' + reponame + '/commit/?id=%hash%'
    elif 'github.com/' in repoval:
        reponame = re.sub('^.*github.com/', '', repoval)
        reponame = re.sub('.git$', '', reponame)
        layer.vcs_web_url = 'http://github.com/' + reponame
        layer.vcs_web_tree_base_url = 'http://github.com/' + reponame + '/tree/%branch%/'
        layer.vcs_web_file_base_url = 'http://github.com/' + reponame + '/blob/%branch%/'
        layer.vcs_web_commit_url = 'http://github.com/' + reponame + '/commit/%hash%'
    elif 'gitlab.com/' in repoval:
        reponame = re.sub('^.*gitlab.com/', '', repoval)
        reponame = re.sub('.git$', '', reponame)
        layer.vcs_web_url = 'http://gitlab.com/' + reponame
        layer.vcs_web_tree_base_url = 'http://gitlab.com/' + reponame + '/tree/%branch%/'
        layer.vcs_web_file_base_url = 'http://gitlab.com/' + reponame + '/blob/%branch%/'
        layer.vcs_web_commit_url = 'http://gitlab.com/' + reponame + '/commit/%hash%'
    elif 'bitbucket.org/' in repoval:
        reponame = re.sub('^.*bitbucket.org/', '', repoval)
        reponame = re.sub('.git$', '', reponame)
        layer.vcs_web_url = 'http://bitbucket.org/' + reponame
        layer.vcs_web_tree_base_url = 'http://bitbucket.org/' + reponame + '/src/%branch%/%path%?at=%branch%'
        layer.vcs_web_file_base_url = 'http://bitbucket.org/' + reponame + '/src/%branch%/%path%?at=%branch%'
        layer.vcs_web_commit_url = 'http://bitbucket.org/' + reponame + '/commits/%hash%'


def readme_extract(readmefn):
    maintainer_re = re.compile('maintaine[r(s)ed by]*[:\n\r]', re.IGNORECASE)
    deps_re = re.compile('depend[sencies upon]*[:\n\r]', re.IGNORECASE)

    maintlines = []
    deps = []
    desc = ''
    maint_mode = False
    blank_seen = False
    deps_mode = False
    desc_mode = True
    with open(readmefn, 'r') as f:
        for line in f.readlines():
            if deps_mode:
                if maintainer_re.search(line):
                    deps_mode = False
                else:
                    if ':' in line:
                        blank_seen = False
                        if line.startswith('URI:'):
                            deps.append(line.split(':', 1)[-1].strip())
                        if line.startswith('layers:'):
                            deps[len(deps)-1] = (deps[len(deps)-1], line.split(':', 1)[-1].strip())
                    elif not (line.startswith('====') or line.startswith('----')):
                        if blank_seen:
                            deps_mode = False
                        else:
                            blank_seen = True
                    continue

            if maint_mode:
                line = line.strip()
                if line and '@' in line or ' at ' in line:
                    maintlines.append(line)
                elif not (line.startswith('====') or line.startswith('----')):
                    if maintlines or blank_seen:
                        maint_mode = False
                    else:
                        blank_seen = True
            elif maintainer_re.search(line):
                desc_mode = False
                maint_mode = True
                blank_seen = False
                if ':' in line:
                    line = line.rsplit(":", 1)[-1].strip()
                    if line:
                        maintlines.append(line)
            elif deps_re.search(line):
                desc_mode = False
                deps_mode = True
                blank_seen = False
            elif desc_mode:
                if not line.strip():
                    if blank_seen:
                        desc_mode = False
                    blank_seen = True
                elif line.startswith('====') or line.startswith('----'):
                    # Assume we just got the title, we don't need that
                    desc = ''
                else:
                    desc += line

    maintainers = []
    for line in maintlines:
        for maint in line.split(','):
            if '@' in maint or ' at ' in maint and not 'yyyyyy@zzzzz.com' in maint:
                maintainers.append(maint.strip())
    return desc, maintainers, deps


def maintainers_extract(maintfn):
    maintainers = []
    with open(maintfn, 'r') as f:
        for line in f.readlines():
            if line.startswith('M:'):
                line = line.split(':', 1)[-1].strip()
                if line and '@' in line or ' at ' in line:
                    maintainers.append(line)
    return list(set(maintainers))


def get_github_layerinfo(layer_url, username = None, password = None):
    import http.client
    import json
    from layerindex.models import LayerMaintainer

    def github_api_call(path):
        conn = http.client.HTTPSConnection('api.github.com')
        headers = {"User-Agent": "test_github.py"}
        if username:
            import base64
            auth = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
            headers['Authorization'] = "Basic %s" % auth

        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        return resp

    json_data = None
    owner_json_data = None

    if layer_url.endswith('.git'):
        layer_url = layer_url[:-4]
    resp = github_api_call('/repos/%s' % layer_url.split('github.com/')[-1].rstrip('/'))
    if resp.status in [200, 302]:
        data = resp.read().decode('utf-8')
        json_data = json.loads(data)
        #headers = dict((key, value) for key, value in resp.getheaders())
        #print(headers)
        owner_resp = github_api_call(json_data['owner']['url'].split('api.github.com')[-1])
        if resp.status in [200, 302]:
            owner_data = owner_resp.read().decode('utf-8')
            owner_json_data = json.loads(owner_data)
        else:
            logger.error('HTTP status %s reading owner info from github API: %s' % (resp.status, resp.read().decode('utf-8')))
    else:
        logger.error('HTTP status %s reading repo info from github API: %s' % (resp.status, resp.read().decode('utf-8')))

    return (json_data, owner_json_data)

def get_layer_type_choices():
    """
    Return help string and choices for --type.
    """
    from layerindex.models import LayerItem
    help_str = "Specify layer type."
    choices = []
    for i in LayerItem.LAYER_TYPE_CHOICES:
        key, description = i
        help_str += ' %s: %s,' % (key, description)
        choices.append(key)

    help_str = help_str.rstrip(',')
    choices.append('')

    return (help_str, choices)

def main():
    valid_layer_name = re.compile('[-\w]+$')

    parser = optparse.OptionParser(
        usage = """
    %prog [options] <url> [name]""")

    utils.setup_django()
    layer_type_help, layer_type_choices = get_layer_type_choices()

    parser.add_option("-s", "--subdir",
            help = "Specify subdirectory",
            action="store", dest="subdir")
    parser.add_option("-t", "--type",
            help = layer_type_help,
            choices = layer_type_choices,
            action="store", dest="layer_type", default='')
    parser.add_option("-n", "--dry-run",
            help = "Don't write any data back to the database",
            action="store_true", dest="dryrun")
    parser.add_option("-d", "--debug",
            help = "Enable debug output",
            action="store_const", const=logging.DEBUG, dest="loglevel", default=logging.INFO)
    parser.add_option("", "--github-auth",
            help = "Specify github username:password",
            action="store", dest="github_auth")
    parser.add_option("-q", "--quiet",
            help = "Hide all output except error messages",
            action="store_const", const=logging.ERROR, dest="loglevel")
    parser.add_option("-a", "--actual-branch",
            help = "Set actual branch",
            action="store", dest="actual_branch")

    options, args = parser.parse_args(sys.argv)

    if len(args) < 2:
        print("Please specify URL of repository for layer")
        sys.exit(1)

    layer_url = args[1]

    if len(args) > 2:
        layer_name = args[2]
    else:
        if options.subdir:
            layer_name = options.subdir
        else:
            layer_name = [x for x in layer_url.split('/') if x][-1]
            if layer_name.endswith('.git'):
                layer_name = layer_name[:-4]

    if not valid_layer_name.match(layer_name):
        logger.error('Invalid layer name "%s" -  Layer name can only include letters, numbers and dashes.', layer_name)
        sys.exit(1)

    if options.github_auth:
        if not ':' in options.github_auth:
            logger.error('--github-auth value must be specified as username:password')
            sys.exit(1)
        splitval = options.github_auth.split(':')
        github_login = splitval[0]
        github_password = splitval[1]
    else:
        github_login = None
        github_password = None

    import settings
    from layerindex.models import LayerItem, LayerBranch, LayerDependency, LayerMaintainer
    from django.db import transaction

    logger.setLevel(options.loglevel)

    fetchdir = settings.LAYER_FETCH_DIR
    if not fetchdir:
        logger.error("Please set LAYER_FETCH_DIR in settings.py")
        sys.exit(1)

    if not os.path.exists(fetchdir):
        os.makedirs(fetchdir)

    master_branch = utils.get_branch('master')
    core_layer = None
    try:
        with transaction.atomic():
            # Fetch layer
            logger.info('Fetching repository %s' % layer_url)

            layer = LayerItem()
            layer.name = layer_name
            layer.status = 'P'
            layer.summary = 'tempvalue'
            layer.description = layer.summary

            set_vcs_fields(layer, layer_url)

            urldir = layer.get_fetch_dir()
            repodir = os.path.join(fetchdir, urldir)
            out = None
            try:
                if not os.path.exists(repodir):
                    out = utils.runcmd(['git', 'clone', layer.vcs_url, urldir], fetchdir, logger=logger)
                else:
                    out = utils.runcmd(['git', 'fetch'], repodir, logger=logger)
            except Exception as e:
                logger.error("Fetch failed: %s" % str(e))
                sys.exit(1)

            actual_branch = 'master'
            if (options.actual_branch):
                actual_branch = options.actual_branch
            try:
                out = utils.runcmd(['git', 'checkout', 'origin/%s' % actual_branch], repodir, logger=logger)
            except subprocess.CalledProcessError:
                actual_branch = None
                branches = utils.runcmd(['git', 'branch', '-r'], repodir, logger=logger)
                for line in branches.splitlines():
                    if 'origin/HEAD ->' in line:
                        actual_branch = line.split('-> origin/')[-1]
                        break
                if not actual_branch:
                    logger.error("Repository has no master branch nor origin/HEAD")
                    sys.exit(1)
                out = utils.runcmd(['git', 'checkout', 'origin/%s' % actual_branch], repodir, logger=logger)

            layer_paths = []
            if options.subdir:
                layerdir = os.path.join(repodir, options.subdir)
                if not os.path.exists(layerdir):
                    logger.error("Subdirectory %s does not exist in repository for master branch" % options.subdir)
                    sys.exit(1)
                if not os.path.exists(os.path.join(layerdir, 'conf/layer.conf')):
                    logger.error("conf/layer.conf not found in subdirectory %s" % options.subdir)
                    sys.exit(1)
                layer_paths.append(layerdir)
            else:
                if os.path.exists(os.path.join(repodir, 'conf/layer.conf')):
                    layer_paths.append(repodir)
                # Find subdirs with a conf/layer.conf
                for subdir in os.listdir(repodir):
                    subdir_path = os.path.join(repodir, subdir)
                    if os.path.isdir(subdir_path):
                        if os.path.exists(os.path.join(subdir_path, 'conf/layer.conf')):
                            layer_paths.append(subdir_path)
                if not layer_paths:
                    logger.error("conf/layer.conf not found in repository or first level subdirectories - is subdirectory set correctly?")
                    sys.exit(1)

            if 'github.com' in layer.vcs_url:
                json_data, owner_json_data = get_github_layerinfo(layer.vcs_url, github_login, github_password)

            for layerdir in layer_paths:
                layer.pk = None
                if layerdir != repodir:
                    subdir = os.path.relpath(layerdir, repodir)
                    if len(layer_paths) > 1:
                        layer.name = subdir
                else:
                    subdir = ''
                if LayerItem.objects.filter(name=layer.name).exists():
                    if LayerItem.objects.filter(name=layer.name).exclude(vcs_url=layer.vcs_url).exists():
                        conflict_list = LayerItem.objects.filter(name=layer.name).exclude(vcs_url=layer.vcs_url)
                        conflict_list_urls = []
                        for conflict in conflict_list:
                            conflict_list_urls.append(conflict.vcs_url)
                        cln = ', '.join(conflict_list_urls)
                        logger.error('A layer named "%s" already exists in the database.  Possible name collision with %s.vcs_url = %s' % (layer.name, layer.name, cln))
                        sys.exit(1)
                    else:
                        logger.info('The layer named "%s" already exists in the database. Skipping this layer with same vcs_url' % layer.name)
                        layer_paths = [x for x in layer_paths if x != layerdir]
                        continue



                logger.info('Creating layer %s' % layer.name)
                # Guess layer type if not specified
                if options.layer_type:
                    layer.layer_type = options.layer_type
                elif layer.name in ['openembedded-core', 'meta-oe']:
                    layer.layer_type = 'A'
                elif glob.glob(os.path.join(layerdir, 'conf/distro/*.conf')):
                    layer.layer_type = 'D'
                elif glob.glob(os.path.join(layerdir, 'conf/machine/*.conf')):
                    layer.layer_type = 'B'
                else:
                    layer.layer_type = 'M'

                layer.save()
                layerbranch = LayerBranch()
                layerbranch.layer = layer
                layerbranch.branch = master_branch
                if layerdir != repodir:
                    layerbranch.vcs_subdir = subdir
                if actual_branch:
                    layerbranch.actual_branch = actual_branch
                layerbranch.save()
                if layer.name != settings.CORE_LAYER_NAME:
                    if not core_layer:
                        core_layer = utils.get_layer(settings.CORE_LAYER_NAME)

                    if core_layer:
                        logger.debug('Adding dep %s to %s' % (core_layer.name, layer.name))
                        layerdep = LayerDependency()
                        layerdep.layerbranch = layerbranch
                        layerdep.dependency = core_layer
                        layerdep.save()
                    layerconfparser = LayerConfParse(logger=logger)
                    try:
                        config_data = layerconfparser.parse_layer(layerdir)
                        if config_data:
                            utils.add_dependencies(layerbranch, config_data, logger=logger)
                            utils.add_recommends(layerbranch, config_data, logger=logger)
                    finally:
                        layerconfparser.shutdown()

                # Get some extra meta-information
                readme_files = glob.glob(os.path.join(layerdir, 'README*'))
                if (not readme_files) and subdir:
                    readme_files = glob.glob(os.path.join(repodir, 'README*'))
                maintainer_files = glob.glob(os.path.join(layerdir, 'MAINTAINERS'))
                if (not maintainer_files) and subdir:
                    maintainer_files = glob.glob(os.path.join(repodir, 'MAINTAINERS'))

                maintainers = []
                if readme_files:
                    (desc, maintainers, deps) = readme_extract(readme_files[0])
                    if desc:
                        layer.summary = layer.name
                        layer.description = desc
                if maintainer_files:
                    maintainers.extend(maintainers_extract(readme_files[0]))

                if (not maintainers) and 'github.com' in layer.vcs_url:
                    if json_data:
                        layer.summary = json_data['description']
                        layer.description = layer.summary
                    if owner_json_data:
                        owner_name = owner_json_data.get('name', None)
                        owner_email = owner_json_data.get('email', None)
                        if owner_name and owner_email:
                            maintainers.append('%s <%s>' % (owner_name, owner_email))

                if layer.name == 'openembedded-core':
                    layer.summary = 'Core metadata'
                elif layer.name == 'meta-oe':
                    layer.summary = 'Additional shared OE metadata'
                    layer.description = layer.summary

                if maintainers:
                    maint_re = re.compile(r'^"?([^"@$<>]+)"? *<([^<> ]+)>[ -]*(.+)?$')
                    for maintentry in maintainers:
                        res = maint_re.match(maintentry)
                        if res:
                            maintainer = LayerMaintainer()
                            maintainer.layerbranch = layerbranch
                            maintainer.name = res.group(1).strip()
                            maintainer.email = res.group(2)
                            if res.group(3):
                                maintainer.responsibility = res.group(3).strip()
                            maintainer.save()

                layer.save()

            if not layer_paths:
                logger.error('No layers added.')
                sys.exit(1);

            if options.dryrun:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
