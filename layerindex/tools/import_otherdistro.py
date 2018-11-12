#!/usr/bin/env python3

# Import other distro information
#
# Copyright (C) 2013, 2018 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details


import sys
import os
import argparse
import logging
from datetime import datetime
import re
import tempfile
import glob
import shutil
import subprocess
from distutils.version import LooseVersion

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), 'lib')))

import utils
import recipeparse

logger = utils.logger_create('LayerIndexOtherDistro')


class DryRunRollbackException(Exception):
    pass


def get_gourl(goipath):
    # Much more crude than the original implementation
    gourl = goipath
    if not '://' in gourl:
        gourl = 'https://' + gourl
    return gourl


def update_recipe_file(path, recipe, repodir, raiseexceptions=False):
    from layerindex.models import Patch, Source
    from django.db import DatabaseError

    # yes, yes, I know this is all crude as hell, but it gets the job done.
    # At the end of the day we are scraping the spec file, we aren't trying to build it

    try:
        logger.debug('Updating recipe %s' % path)
        recipe.pn = os.path.splitext(recipe.filename)[0]
        with open(path, 'r', errors='surrogateescape') as f:
            indesc = False
            desc = []
            patches = []
            sources = []
            values = {}
            defines = {'__awk': 'awk',
                      '__python3': 'python3',
                      '__python2': 'python',
                      '__python': 'python',
                      '__sed': 'sed',
                      '__perl': 'perl',
                      '__id_u': 'id -u',
                      '__cat': 'cat',
                      '__grep': 'grep',
                      '_bindir': '/usr/bin',
                      '_sbindir': '/usr/sbin',
                      '_datadir': '/usr/share',
                      '_docdir': '%{datadir}/doc',
                      '_defaultdocdir': '%{datadir}/doc',
                      '_pkgdocdir': '%{_docdir}/%{name}'
                     }
            globaldefs = {}

            def expand(expr):
                inmacro = 0
                inshell = 0
                lastch = None
                macroexpr = ''
                shellexpr = ''
                outstr = ''
                for i, ch in enumerate(expr):
                    if inshell:
                        if ch == '(':
                            inshell += 1
                        elif ch == ')':
                            inshell -= 1
                            if inshell == 0:
                                try:
                                    shellcmd = expand(shellexpr)
                                    expanded = subprocess.check_output(shellcmd, shell=True).decode('utf-8').rstrip()
                                except Exception as e:
                                    logger.warning('Failed to execute "%s": %s' % (shellcmd, str(e)))
                                    expanded = ''
                                if expanded:
                                    outstr += expanded
                                lastch = ch
                                continue
                        shellexpr += ch
                    elif inmacro:
                        if ch == '}':
                            inmacro -= 1
                            if inmacro == 0:
                                if macroexpr.startswith('?'):
                                    macrosplit = macroexpr[1:].split(':')
                                    macrokey = macrosplit[0].lower()
                                    if macrokey in globaldefs or macrokey in defines or macrokey in values:
                                        if len(macrosplit) > 1:
                                            outstr += expand(macrosplit[1])
                                        else:
                                            expanded = expand(values.get(macrokey, '') or defines.get(macrokey, '') or globaldefs.get(macrokey, ''))
                                            if expanded:
                                                outstr += expanded
                                elif macroexpr.startswith('!?'):
                                    macrosplit = macroexpr[2:].split(':')
                                    macrokey = macrosplit[0].lower()
                                    if len(macrosplit) > 1:
                                        if not (macrokey in globaldefs or macrokey in defines or macrokey in values):
                                            outstr += expand(macrosplit[1])
                                else:
                                    macrokey = macroexpr.lower()
                                    expanded = expand(values.get(macrokey, '') or defines.get(macrokey, '') or globaldefs.get(macrokey, ''))
                                    if expanded:
                                        outstr += expanded
                                    else:
                                        outstr += '%{' + macroexpr + '}'
                                lastch = ch
                                continue
                        macroexpr += ch
                    if ch == '{':
                        if lastch == '%':
                            if inmacro == 0:
                                macroexpr = ''
                                outstr = outstr[:-1]
                            inmacro += 1
                    elif ch == '(':
                        if lastch == '%':
                            if inshell == 0:
                                shellexpr = ''
                                outstr = outstr[:-1]
                            inshell += 1
                    if inmacro == 0 and inshell == 0:
                        if ch == '%':
                            # Handle unbracketed expressions (in which case we eat the rest of the expression)
                            if expr[i+1] not in ['{', '%']:
                                macrokey = expr[i+1:].split()[0]
                                if macrokey in globaldefs or macrokey in defines or macrokey in values:
                                    expanded = expand(values.get(macrokey, '') or defines.get(macrokey, '') or globaldefs.get(macrokey, ''))
                                    if expanded:
                                        outstr += expanded
                                        break
                        if ch == '%' and lastch == '%':
                            # %% is a literal %, so skip this one (and don't allow this to happen again if the next char is a %)
                            lastch = ''
                            continue
                        outstr += ch
                    lastch = ch
                return outstr

            def eval_cond(cond, condtype):
                negate = False
                if condtype == '%if':
                    if cond.startswith('(') and cond.endswith(')'):
                        cond = cond[1:-1].strip()
                    if cond.startswith('!'):
                        cond = cond[1:].lstrip()
                        negate = True
                    res = False
                    try:
                        if int(cond):
                            res = True
                    except ValueError:
                        pass
                elif condtype in ['%ifos', '%ifnos']:
                    if condtype == '%ifnos':
                        negate = True
                    # Assume linux
                    res = ('linux' in cond.split())
                elif condtype in ['%ifarch', '%ifnarch']:
                    if condtype == '%ifnarch':
                        negate = True
                    res = ('x86_64' in cond.split())
                else:
                    raise Exception('Unhandled conditional type "%s"' % condtype)
                if negate:
                    return not res
                else:
                    return res

            conds = []
            reading = True
            for line in f:
                if line.startswith('%package'):
                    # Assume it's OK to stop when we hit the first package
                    break
                if line.startswith(('%gometa', '%gocraftmeta')):
                    goipath = globaldefs.get('goipath', '')
                    if not goipath:
                        goipath = globaldefs.get('gobaseipath', '')
                    if goipath:
                        # We could use a python translation of the full logic from
                        # the RPM macros to get this - but it turns out the spec files
                        # (in Fedora at least) already use these processed names, so
                        # there's no point
                        globaldefs['goname'] = os.path.splitext(os.path.basename(path))[0]
                        globaldefs['gourl'] = get_gourl(goipath)
                elif line.startswith('%if') and ' ' in line:
                    conds.append(reading)
                    splitline = line.split()
                    cond = expand(' '.join(splitline[1:]))
                    if not eval_cond(cond, splitline[0]):
                        reading = False
                elif line.startswith('%else'):
                    reading = not reading
                elif line.startswith('%endif'):
                    reading = conds.pop()
                if not reading:
                    continue
                if line.startswith(('%define', '%global')):
                    linesplit = line.split()
                    name = linesplit[1].lower()
                    value = ' '.join(linesplit[2:])
                    if value.lower() == '%{' + name + '}':
                        # STOP THE INSANITY!
                        # (as seen in cups/cups.spec in Fedora)
                        continue
                    if line.startswith('%global'):
                        globaldefs[name] = expand(value)
                    else:
                        defines[name] = value
                    continue
                elif line.startswith('%undefine'):
                    linesplit = line.split()
                    name = linesplit[1].lower()
                    if name in globaldefs:
                        del globaldefs[name]
                    if name in defines:
                        del defines[name]
                    continue
                elif line.strip() == '%description':
                    indesc = True
                    continue
                if indesc:
                    # We want to stop parsing the description when we hit another macro,
                    # but we do want to allow bracketed macro expressions within the description
                    # (e.g. %{name})
                    if line.startswith('%') and len(line) > 1 and line[1] != '{':
                        indesc = False
                    elif not line.startswith('#'):
                        desc.append(line)

                if ':' in line and not line.startswith('%'):
                    key, value = line.split(':', 1)
                    key = key.rstrip().lower()
                    value = value.strip()
                    values[key] = expand(value)

        for key, value in values.items():
            if key == 'name':
                recipe.pn = expand(value)
            elif key == 'version':
                recipe.pv = expand(value)
            elif key == 'summary':
                recipe.summary = expand(value.strip('"\''))
            elif key == 'group':
                recipe.section = expand(value)
            elif key == 'url':
                recipe.homepage = expand(value)
            elif key == 'license':
                recipe.license = expand(value)
            elif key.startswith('patch'):
                patches.append((int(key[5:] or '0'), expand(value)))
            elif key.startswith('source'):
                sources.append(expand(value))

        recipe.description = expand(' '.join(desc).rstrip())
        recipe.save()

        saved_patches = []
        for index, patchfn in patches:
            patchpath = os.path.join(os.path.relpath(os.path.dirname(path), repodir), patchfn)
            patch, _ = Patch.objects.get_or_create(recipe=recipe, path=patchpath)
            patch.src_path = patchfn
            patch.apply_order = index
            patch.save()
            saved_patches.append(patch.id)
        recipe.patch_set.exclude(id__in=saved_patches).delete()

        existing_ids = list(recipe.source_set.values_list('id', flat=True))
        for src in sources:
            srcobj, _ = Source.objects.get_or_create(recipe=recipe, url=src)
            srcobj.save()
            if srcobj.id in existing_ids:
                existing_ids.remove(srcobj.id)
        # Need to delete like this because some spec files have a lot of sources!
        for idv in existing_ids:
            Source.objects.filter(id=idv).delete()
    except DatabaseError:
        raise
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        if raiseexceptions:
            raise
        else:
            if not recipe.pn:
                recipe.pn = recipe.filename[:-3].split('_')[0]
            logger.error("Unable to read %s: %s", path, str(e))


def check_branch_layer(args):
    from layerindex.models import LayerItem, LayerBranch

    branch = utils.get_branch(args.branch)
    if not branch:
        logger.error("Specified branch %s is not valid" % args.branch)
        return 1, None

    res = list(LayerItem.objects.filter(name=args.layer)[:1])
    if res:
        layer = res[0]
    else:
        logger.error('Cannot find specified layer "%s"' % args.layer)
        return 1, None

    layerbranch = layer.get_layerbranch(args.branch)
    if not layerbranch:
        # LayerBranch doesn't exist for this branch, create it
        layerbranch = LayerBranch()
        layerbranch.layer = layer
        layerbranch.branch = branch
        layerbranch.save()

    return 0, layerbranch


def get_update_obj(args):
    from layerindex.models import Update
    updateobj = None
    if args.update:
        updateobj = Update.objects.filter(id=int(args.update))
        if not updateobj:
            logger.error("Specified update id %s does not exist in database" % args.update)
            sys.exit(1)
        updateobj = updateobj.first()
    return updateobj


def import_pkgspec(args):
    utils.setup_django()
    import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Machine, BBAppend, BBClass, ComparisonRecipeUpdate
    from django.db import transaction

    ret, layerbranch = check_branch_layer(args)
    if ret:
        return ret

    updateobj = get_update_obj(args)
    logdir = getattr(settings, 'TASK_LOG_DIR')
    if updateobj and updateobj.task_id and logdir:
        pwriter = utils.ProgressWriter(logdir, updateobj.task_id, logger=logger)
    else:
        pwriter = None

    metapath = args.pkgdir

    try:
        with transaction.atomic():
            layerrecipes = ClassicRecipe.objects.filter(layerbranch=layerbranch)

            existing = list(layerrecipes.filter(deleted=False).values_list('filepath', 'filename'))
            dirlist = os.listdir(metapath)
            total = len(dirlist)
            for count, entry in enumerate(dirlist):
                if os.path.exists(os.path.join(metapath, entry, 'dead.package')):
                    logger.info('Skipping dead package %s' % entry)
                    continue
                specfiles = glob.glob(os.path.join(metapath, entry, '*.spec'))
                if specfiles:
                    for specfile in specfiles:
                        specfn = os.path.basename(specfile)
                        specpath = os.path.relpath(os.path.dirname(specfile), metapath)
                        recipe, created = ClassicRecipe.objects.get_or_create(layerbranch=layerbranch, filepath=specpath, filename=specfn)
                        if created:
                            logger.info('Importing %s' % specfn)
                        elif recipe.deleted:
                            logger.info('Restoring and updating %s' % specpath)
                            recipe.deleted = False
                        else:
                            logger.info('Updating %s' % specpath)
                        recipe.layerbranch = layerbranch
                        recipe.filename = specfn
                        recipe.filepath = specpath
                        update_recipe_file(specfile, recipe, metapath)
                        recipe.save()
                        existingentry = (specpath, specfn)
                        if existingentry in existing:
                            existing.remove(existingentry)
                        if updateobj:
                            rupdate, _ = ComparisonRecipeUpdate.objects.get_or_create(update=updateobj, recipe=recipe)
                            rupdate.meta_updated = True
                            rupdate.save()
                else:
                    logger.warn('Missing spec file in %s' % os.path.join(metapath, entry))
                if pwriter:
                    pwriter.write(int(count / total * 100))

            if existing:
                fpaths = ['%s/%s' % (pth, fn) for pth, fn in existing]
                logger.info('Marking as deleted: %s' % ', '.join(fpaths))
                for entry in existing:
                    layerrecipes.filter(filepath=entry[0], filename=entry[1]).update(deleted=True)

            if args.description:
                logger.debug('Setting description to "%s"' % args.description)
                branch = layerbranch.branch
                branch.short_description = args.description
                branch.save()
                layer = layerbranch.layer
                layer.summary = args.description
                layer.save()

            layerbranch.vcs_last_fetch = datetime.now()
            layerbranch.save()

            if args.dry_run:
                raise DryRunRollbackException()
    except DryRunRollbackException:
        pass
    except:
        import traceback
        traceback.print_exc()
        return 1

    return 0


def try_specfile(args):
    utils.setup_django()
    import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Machine, BBAppend, BBClass
    from django.db import transaction

    ret, layerbranch = check_branch_layer(args)
    if ret:
        return ret

    specfile = args.specfile
    metapath = os.path.dirname(specfile)

    try:
        with transaction.atomic():
            recipe = ClassicRecipe()
            recipe.layerbranch = layerbranch
            recipe.filename = os.path.basename(specfile)
            recipe.filepath = os.path.relpath(os.path.dirname(specfile), metapath)
            update_recipe_file(specfile, recipe, metapath, raiseexceptions=True)
            recipe.save()
            for f in Recipe._meta.get_fields():
                if not (f.auto_created and f.is_relation):
                    print('%s: %s' % (f.name, getattr(recipe, f.name)))
            if recipe.source_set.exists():
                print('sources:')
                for src in recipe.source_set.all():
                    print(' * %s' % src.url)

            raise DryRunRollbackException()
    except DryRunRollbackException:
        pass
    except:
        import traceback
        traceback.print_exc()
        return 1

    return 0


def import_deblist(args):
    utils.setup_django()
    import settings
    from layerindex.models import LayerItem, LayerBranch, Recipe, ClassicRecipe, Machine, BBAppend, BBClass
    from django.db import transaction

    ret, layerbranch = check_branch_layer(args)
    if ret:
        return ret

    updateobj = get_update_obj(args)

    try:
        with transaction.atomic():
            layerrecipes = ClassicRecipe.objects.filter(layerbranch=layerbranch)
            existing = list(layerrecipes.filter(deleted=False).values_list('pn', flat=True))

            def handle_pkg(pkg):
                pkgname = pkg['Package']
                recipe, created = ClassicRecipe.objects.get_or_create(layerbranch=layerbranch, pn=pkgname)
                if created:
                    logger.info('Importing %s' % pkgname)
                elif recipe.deleted:
                    logger.info('Restoring and updating %s' % pkgname)
                    recipe.deleted = False
                else:
                    logger.info('Updating %s' % pkgname)
                filename = pkg.get('Filename', '')
                if filename:
                    recipe.filename = os.path.basename(filename)
                    recipe.filepath = os.path.dirname(filename)
                recipe.section = pkg.get('Section', '')
                description = pkg.get('Description', '')
                if description:
                    description = description.splitlines()
                    recipe.summary = description.pop(0)
                    recipe.description = ' '.join(description)
                recipe.pv = pkg.get('Version', '')
                recipe.homepage = pkg.get('Homepage', '')
                recipe.license = pkg.get('License', '')
                recipe.save()
                if pkgname in existing:
                    existing.remove(pkgname)
                if updateobj:
                    rupdate, _ = ComparisonRecipeUpdate.objects.get_or_create(update=updateobj, recipe=recipe)
                    rupdate.meta_updated = True
                    rupdate.save()

            pkgs = []
            pkginfo = {}
            lastfield = ''
            with open(args.pkglistfile, 'r') as f:
                for line in f:
                    linesplit = line.split()
                    if line.startswith('Package:'):
                        # Next package starting, deal with the last one (unless this is the first)
                        if pkginfo:
                            handle_pkg(pkginfo)

                        pkginfo = {}
                        lastfield = 'Package'

                    if line.startswith(' '):
                        if lastfield:
                            pkginfo[lastfield] += '\n' + line.strip()
                    elif ':' in line:
                        field, value = line.split(':', 1)
                        pkginfo[field] = value.strip()
                        lastfield = field
                    else:
                        lastfield = ''
                if pkginfo:
                    # Handle last package
                    handle_pkg(pkginfo)

                if existing:
                    logger.info('Marking as deleted: %s' % ', '.join(existing))
                    layerrecipes.filter(pn__in=existing).update(deleted=True)

                layerbranch.vcs_last_fetch = datetime.now()
                layerbranch.save()

                if args.dry_run:
                    raise DryRunRollbackException()
    except DryRunRollbackException:
        pass
    except:
        import traceback
        traceback.print_exc()
        return 1


def main():

    parser = argparse.ArgumentParser(description='OE Layer Index other distro comparison import tool',
                                        epilog='Use %(prog)s <subcommand> --help to get help on a specific command')
    parser.add_argument('-d', '--debug', help='Enable debug output', action='store_const', const=logging.DEBUG, dest='loglevel', default=logging.INFO)
    parser.add_argument('-q', '--quiet', help='Hide all output except error messages', action='store_const', const=logging.ERROR, dest='loglevel')

    subparsers = parser.add_subparsers(title='subcommands', metavar='<subcommand>')
    subparsers.required = True


    parser_pkgspec = subparsers.add_parser('import-pkgspec',
                                           help='Import from a local rpm-based distro package directory',
                                           description='Imports from a local directory containing subdirectories, each of which contains an RPM .spec file for a package')
    parser_pkgspec.add_argument('branch', help='Branch to import into')
    parser_pkgspec.add_argument('layer', help='Layer to import into')
    parser_pkgspec.add_argument('pkgdir', help='Top level directory containing package subdirectories')
    parser_pkgspec.add_argument('--description', help='Set branch/layer description')
    parser_pkgspec.add_argument('-u', '--update', help='Specify update record to link to')
    parser_pkgspec.add_argument('-n', '--dry-run', help='Don\'t write any data back to the database', action='store_true')
    parser_pkgspec.set_defaults(func=import_pkgspec)


    parser_tryspecfile = subparsers.add_parser('try-specfile',
                                           help='Test importing from a local RPM spec file',
                                           description='Tests importing an RPM .spec file for a package')
    parser_tryspecfile.add_argument('branch', help='Branch to import into')
    parser_tryspecfile.add_argument('layer', help='Layer to import into')
    parser_tryspecfile.add_argument('specfile', help='Spec file to try importing')
    parser_tryspecfile.set_defaults(func=try_specfile)


    parser_deblist = subparsers.add_parser('import-deblist',
                                           help='Import from a list of Debian packages',
                                           description='Imports from a list of Debian packages')
    parser_deblist.add_argument('branch', help='Branch to import into')
    parser_deblist.add_argument('layer', help='Layer to import into')
    parser_deblist.add_argument('pkglistfile', help='File containing a list of packages, as produced by: apt-cache show "*"')
    parser_deblist.add_argument('-u', '--update', help='Specify update record to link to')
    parser_deblist.add_argument('-n', '--dry-run', help='Don\'t write any data back to the database', action='store_true')
    parser_deblist.set_defaults(func=import_deblist)


    args = parser.parse_args()

    logger.setLevel(args.loglevel)

    ret = args.func(args)

    return ret

if __name__ == "__main__":
    main()
