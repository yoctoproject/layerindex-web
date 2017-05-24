# Utility functions for parsing layer.conf using bitbake within layerindex-web
#
# Copyright (C) 2016 Wind River Systems
# Author: Liam R. Howlett <liam.howlett@windriver.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#

import sys
import os
import os.path
import utils
import tempfile
import re

class LayerConfParse:
    def __init__(self, enable_tracking=False, logger=None, bitbakepath=None, tinfoil=None):
        import settings
        self.logger = logger

        if not bitbakepath:
            fetchdir = settings.LAYER_FETCH_DIR
            bitbakepath = os.path.join(fetchdir, 'bitbake')
        self.bbpath = bitbakepath

        # Set up BBPATH.
        os.environ['BBPATH'] = str("%s" % self.bbpath)
        self.tinfoil = tinfoil

        if not self.tinfoil:
            self.tinfoil = utils.setup_tinfoil(self.bbpath, enable_tracking)

        self.config_data_copy = bb.data.createCopy(self.tinfoil.config_data)

    def parse_layer(self, layerdir):

        # This is not a valid layer, parsing will cause exception.
        if not utils.is_layer_valid(layerdir):
            return None

        utils.parse_layer_conf(layerdir, self.config_data_copy, logger=self.logger)
        return self.config_data_copy

    def shutdown(self):
        self.tinfoil.shutdown()


