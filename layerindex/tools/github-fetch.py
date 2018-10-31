#!/usr/bin/env python3

# Github fetch utility

# Copyright (C) 2017 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import argparse
import json
import requests
import re
import subprocess

def fetchall(args):
    link_re = re.compile('<(http[^>]+)>; rel="([a-zA-Z0-9]+)"')

    keys = {'orgname': args.organisation,
            'access_token': args.access_token,
            'per_page': 100
            }
    url = 'https://api.github.com/orgs/{orgname}/repos?access_token={access_token}&per_page={per_page}'
    url = url.format(**keys)

    existing = os.listdir(args.outdir)
    for name in existing:
        if name.endswith('.deleted'):
            print('Directories marked deleted (suffix .deleted) still exist in output path - remove these to continue')
            sys.exit(1)

    if args.resume_from:
        fetching = False
    else:
        fetching = True

    failed = []
    repos = None
    while True:
        session = requests.Session()
        print('getting %s' % url)
        with requests.Session() as s:
            r = s.get(url)
            if not r.ok:
                print('Request failed: %d: %s' % (r.status_code, r.text))
                sys.exit(2)
            st = r.text
            repos = json.loads(st)
            for repo in repos:
                name = repo['name']
                if name in existing:
                    existing.remove(name)
                if args.resume_from and name == args.resume_from:
                    fetching = True
                elif not fetching:
                    print('Skipping %s' % name)
                    continue
                clone_url = repo['clone_url']
                outpath = os.path.join(args.outdir, name)
                if os.path.exists(outpath):
                    print('Update %s' % outpath)
                    ret = subprocess.call(['git', 'fetch'], cwd=outpath)
                    if ret == 0:
                        ret = subprocess.call(['git', 'reset', '--hard', 'FETCH_HEAD'], cwd=outpath)
                else:
                    print('Fetch %s' % clone_url)
                    ret = subprocess.call(['git', 'clone', clone_url, name], cwd=args.outdir)
                if ret != 0:
                    failed.append(name)

            link = r.headers.get('Link', None)
            if link:
                linkitems = dict([reversed(x) for x in link_re.findall(link)])
                url = linkitems.get('next', None)
                if not url:
                    break
            else:
                break

    if not repos:
        print('Something went wrong - no repositories were found')
        sys.exit(1)

    deleted = False
    for dirname in existing:
        dirpath = os.path.join(outpath, dirname)
        print('Marking %s as deleted' % dirname)
        os.rename(dirpath, dirpath + '.deleted')
        deleted = True
    if deleted:
        print('You will need to delete the above marked directories manually')

    if failed:
        print('The following repositories failed to fetch properly:')
        for name in failed:
            try:
                dirlist = os.listdir(os.path.join(args.outdir, name))
            except FileNotFoundError:
                dirlist = None
            if dirlist == [] or dirlist == ['.git']:
                print('%s (empty)' % name)
            else:
                print('%s' % name)


def main():
    parser = argparse.ArgumentParser(description="github fetch utility",
                                        epilog="Use %(prog)s <subcommand> --help to get help on a specific command")
    #parser.add_argument('-d', '--debug', help='Enable debug output', action='store_true')
    subparsers = parser.add_subparsers(title='subcommands', metavar='<subcommand>')
    subparsers.required = True

    parser_fetchall = subparsers.add_parser('fetchall',
                                            help='Fetch/update all repos in a specific github organisation',
                                          description='Fetches/updates all repos in a specific github organisation')
    parser_fetchall.add_argument('organisation', help='Organisation to fetch from')
    parser_fetchall.add_argument('access_token', help='Access token to use')
    parser_fetchall.add_argument('outdir', nargs='?', default='.', help='Output directory')
    parser_fetchall.add_argument('-r', '--resume-from', help='Resume from the specified repository')
    parser_fetchall.set_defaults(func=fetchall)

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
