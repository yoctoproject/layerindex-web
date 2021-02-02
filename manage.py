#!/usr/bin/env python3

# layerindex-web - Django management script
#
# Based on the Django project template
#
# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
#
# SPDX-License-Identifier: MIT

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

