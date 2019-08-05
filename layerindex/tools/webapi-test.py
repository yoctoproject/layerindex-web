#!/usr/bin/env python3

# Layerindex web API test utility

# Copyright (C) 2019 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import argparse
import json
import requests
import subprocess
import tempfile
import shutil
import re

def compare_recipe(args):
    tmpdir = tempfile.mkdtemp()
    try:
        def fetch_json(url, fn):
            fetchurl = url + '/layerindex/api/recipes/?filter=pn:%s' % args.pn
            print('getting %s' % fetchurl)
            r = requests.get(fetchurl)
            if not r.ok:
                print('Request failed: %d: %s' % (r.status_code, r.text))
                sys.exit(2)
            jsdata = json.loads(r.text)
            with open(os.path.join(tmpdir, fn), 'w') as f:
                json.dump(jsdata, f, indent=4, sort_keys=True)
                f.write('\n')

        fetch_json(args.url1, 'file1')
        fetch_json(args.url2, 'file2')

        subprocess.call(['git', 'diff', '--no-index', os.path.join(tmpdir, 'file1'), os.path.join(tmpdir, 'file2')], shell=False)
    finally:
        shutil.rmtree(tmpdir)


def main():
    parser = argparse.ArgumentParser(description="github fetch utility",
                                        epilog="Use %(prog)s <subcommand> --help to get help on a specific command")
    #parser.add_argument('-d', '--debug', help='Enable debug output', action='store_true')
    subparsers = parser.add_subparsers(title='subcommands', metavar='<subcommand>')
    subparsers.required = True

    parser_compare_recipe = subparsers.add_parser('compare-recipe',
                                                  help='Compare recipe JSON from two different layer index instances',
                                                  description='Compares recipe JSON from two different layer index instances')
    parser_compare_recipe.add_argument('url1', help='First layer index URL to fetch from')
    parser_compare_recipe.add_argument('url2', help='Second layer index URL to fetch from')
    parser_compare_recipe.add_argument('pn', help='Recipe name to compare')
    parser_compare_recipe.set_defaults(func=compare_recipe)

    args = parser.parse_args()

    ret = args.func(args)

    return ret


if __name__ == "__main__":
    try:
        ret = main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
