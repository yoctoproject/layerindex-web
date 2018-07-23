#!/usr/bin/env python3

# Fedora Pagure (e.g. https://src.fedoraproject.org/) fetch utility

# Copyright (C) 2017, 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import argparse
import json
import requests
import re
import subprocess


def get_repos_api(url, toplevel_item=None, name_attr='name', use_link_header=True, link_item='pagination', link_next_attr='next'):
    link_re = re.compile('<(http[^>]+)>; rel="([a-zA-Z0-9]+)"')
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
            jdata = json.loads(st)
            if toplevel_item:
                repos = jdata[toplevel_item]
            else:
                repos = jdata
            for repo in repos:
                name = repo[name_attr]
                yield repo

            link_url = None
            if use_link_header:
                link = r.headers.get('Link', None)
                if link:
                    linkitems = dict([reversed(x) for x in link_re.findall(link)])
                    link_url = linkitems.get('next', None)
            else:
                link = jdata.get(link_item, None)
                if link:
                    link_url = link.get(link_next_attr, None)
            if not link_url:
                break
            url = link_url


def fetchall(args):

    site = args.site
    if site.endswith('/'):
        site = site[:-1]

    keys = {'site': site,
            'start_page': args.resume_page,
            'per_page': 100
            }
    url = '{site}/api/0/projects?page={start_page}&per_page={per_page}'
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
    gotsomething = False
    for repo in get_repos_api(url, toplevel_item='projects', use_link_header=False, link_item='pagination', link_next_attr='next'):
        gotsomething = True
        if repo['parent']:
            print('ignoring %s' % repo['fullname'])
            continue
        if not repo['fullname'].startswith('rpms/'):
            print('ignoring %s' % repo['fullname'])
            continue
        name = repo['name']
        clone_url = site + '/' + repo['url_path'] + '.git'
        if name in existing:
            existing.remove(name)
        if args.resume_from and name == args.resume_from:
            fetching = True
        elif not fetching:
            print('Skipping %s' % name)
            continue

        outpath = os.path.join(args.outdir, name)
        for retry in [0, 1]:
            if os.path.exists(outpath):
                print('Update %s' % outpath)
                ret = subprocess.call(['git', 'pull'], cwd=outpath)
            else:
                print('Fetch %s' % clone_url)
                ret = subprocess.call(['git', 'clone', clone_url, name], cwd=args.outdir)
            if ret == 0:
                break
        if ret != 0:
            failed.append(name)

    if not gotsomething:
        print('Something went wrong - no repositories were found')
        sys.exit(1)

    if not args.resume_page:
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
    parser = argparse.ArgumentParser(description="Fedora package source fetch utility",
                                        epilog="Use %(prog)s <subcommand> --help to get help on a specific command")
    #parser.add_argument('-d', '--debug', help='Enable debug output', action='store_true')
    subparsers = parser.add_subparsers(title='subcommands', metavar='<subcommand>')
    subparsers.required = True

    parser_fetchall = subparsers.add_parser('fetchall',
                                            help='Fetch/update all repos from Fedora\'s pagure instance',
                                          description='Fetches/updates all repos in a pagure instance')
    parser_fetchall.add_argument('site', nargs='?', default='https://src.fedoraproject.org', help='URL to Pagure site (default %(default)s)')
    parser_fetchall.add_argument('outdir', nargs='?', default='.', help='Output directory (default %(default)s)')
    parser_fetchall.add_argument('-r', '--resume-from', help='Resume from the specified repository')
    parser_fetchall.add_argument('-p', '--resume-page', default='1', help='Resume from the specified page (disables deleting)')
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
