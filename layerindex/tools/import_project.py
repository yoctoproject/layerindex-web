#!/usr/bin/python3

# Import a project into the database.
#  This will scan through the directories in a project and find any layer and
#  call import_layer.
#
#
# Copyright (C) 2016 Wind River Systems
# Author: Liam R. Howlett <liam.howlett@windriver.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

from urllib.parse import urlparse
import logging
import optparse
import os, fnmatch
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

import import_layer
import update

import utils




class ImportProject:
    logger = utils.logger_create('ProjectIndexImport')

    def find_layers(self, path):
        self.logger.debug("finding layer..")
        result = []
        for root, _, files in os.walk(path, followlinks=True):
            for _ in fnmatch.filter(files, 'layer.conf'):
                if not root.endswith('conf'):
                    continue

                self.logger.debug("Found %s" % root)
                result.append(root)
        return result


    def main(self):
        parser = optparse.OptionParser(
            usage="""
            %prog [options] [directory]""")

        parser.add_option("-d", "--debug",
            help="Enable debug output",
            action="store_const", const=logging.DEBUG,
            dest="loglevel", default=logging.INFO)
        parser.add_option("-n", "--dry-run",
            help="Don't write any data back to the database",
            action="store_true", dest="dryrun")

        self.options, args = parser.parse_args(sys.argv)

        self.logger.setLevel(self.options.loglevel)

        if len(args) == 1:
            print("Please provide a directory.")
            sys.exit(1)

        install_dir = args[1]
        lc_list = self.find_layers(install_dir)
        core_layer = self.add_core(lc_list)
        if core_layer:
            lc_list.remove(core_layer)



        for layer in lc_list:
            self.add_layer(layer)

    def add_layer(self, layer):
        self.logger.debug("Processing layer %s" % layer)
        try:
            git_dir = utils.runcmd(['git', 'rev-parse', '--show-toplevel'], destdir=layer, logger=self.logger)
        except Exception as e:
            self.logger.error("Cannot get root dir for layer %s: %s - Skipping." % (layer, str(e)))
            return 1


        layer_name = layer.split('/')[-2]


        layer_subdir = None
        if os.path.basename(git_dir) != layer_name:
            layer_subdir = layer_name

        layer_name = self.get_layer_name(layer)

        for i in [1, 2, 3]:
            remote = utils.runcmd(['git', 'remote'], destdir=git_dir, logger=self.logger)
            if not remote:
                self.logger.warning("Cannot find remote git for %s" % layer_name)
                return 1

            try:
                git_url = utils.runcmd(['git', 'config', '--get', 'remote.%s.url' % remote], destdir=git_dir, logger=self.logger)
            except Exception as e:
                self.logger.info("Cannot get remote.%s.url for git dir %s: %s" % (remote, git_dir, str(e)))

            if not os.path.exists(git_url):
                # Assume this is remote.
                self.logger.debug("Found git url = %s" % git_url)
                remote_branch = utils.runcmd(['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], destdir=git_dir, logger=self.logger)
                if remote_branch.startswith(remote):
                    actual_branch = remote_branch[len(remote) + 1:]
                break
            self.logger.debug("Iterating to find git url into %s" % git_dir)
            git_dir = git_url

        if not git_url:
            self.logger.warning("Cannot find layer %s git url" % layer)
            return 1

        cmd = ['import_layer.py']
        if self.options.loglevel == logging.DEBUG:
            cmd.append("-d")
        if layer_subdir:
            cmd.append("-s")
            cmd.append(layer_subdir)

        if actual_branch:
            cmd.append("-a")
            cmd.append(actual_branch)
        cmd.append(git_url)
        cmd.append(layer_name)
        prefix = "Calling"

        if self.options.dryrun:
            prefix = "Would Call"


        self.logger.info("%s import_layer.main with %s for dir %s" % (prefix, str(cmd), layer))
        sys.argv = cmd
        if not self.options.dryrun:
            try:
                import_layer.main()
            except SystemExit as see:
                return see.code
        return 0

    def get_layer_name(self, layerconfdir):
        layer_name = layerconfdir.split('/')[-2]
        self.logger.debug('getting layer %s' % layerconfdir)
        layer_conf = os.path.join(layerconfdir, 'layer.conf')
        if os.path.isfile(layer_conf):
            with open(layer_conf) as conf:
                for line in conf:
                    if 'BBLAYERS_LAYERINDEX_NAME' in line:
                        layer_name = line.split('=')[1].strip(' "\n')
        return layer_name

    def add_core(self, layers):
        utils.setup_django()
        core = None
        import settings
        for layer in layers:
            layer_name = self.get_layer_name(layer)
            if layer_name == settings.CORE_LAYER_NAME:
                if self.add_layer(layer):
                    self.logger.info('Failed to add core layer\n')
                core = layer
                self.update()
                break
        return core

    def update(self):
        update_py = os.path.realpath(os.path.join(os.path.dirname(__file__), '../update.py'))
        cmd = [update_py]
        if self.options.loglevel == logging.DEBUG:
            cmd.append("-d")
        sys.argv = cmd
        self.logger.info("update")
        if not self.options.dryrun:
            try:
                update.main()
            except SystemExit:
                return 1

        return 0


if __name__ == "__main__":
    x = ImportProject()
    x.main()
