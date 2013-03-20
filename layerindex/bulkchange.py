#!/usr/bin/env python

# layerindex-web - bulk change implementation
#
# Copyright (C) 2013 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

import sys
import os
import os.path
import tempfile
import tarfile
import textwrap
import difflib
import recipeparse
import utils
import shutil
from django.utils.datastructures import SortedDict

logger = utils.logger_create('LayerIndexImport')

# Help us to find places to insert values
recipe_progression = ['SUMMARY', 'DESCRIPTION', 'HOMEPAGE', 'BUGTRACKER', 'SECTION', 'LICENSE', 'LIC_FILES_CHKSUM', 'PROVIDES', 'DEPENDS', 'PR', 'PV', 'SRC_URI', 'do_fetch', 'do_unpack', 'do_patch', 'EXTRA_OECONF', 'do_configure', 'EXTRA_OEMAKE', 'do_compile', 'do_install', 'do_populate_sysroot', 'INITSCRIPT', 'USERADD', 'GROUPADD', 'PACKAGES', 'FILES', 'RDEPENDS', 'RRECOMMENDS', 'RSUGGESTS', 'RPROVIDES', 'RREPLACES', 'RCONFLICTS', 'ALLOW_EMPTY', 'do_package', 'do_deploy']
# Variables that sometimes are a bit long but shouldn't be wrapped
nowrap_vars = ['SUMMARY', 'HOMEPAGE', 'BUGTRACKER', 'LIC_FILES_CHKSUM']
meta_vars = ['SUMMARY', 'DESCRIPTION', 'HOMEPAGE', 'BUGTRACKER', 'SECTION']

def generate_patches(tinfoil, fetchdir, changeset, outputdir):
    tmpoutdir = tempfile.mkdtemp(dir=outputdir)
    last_layer = None
    patchname = ''
    patches = []
    outfile = None
    try:
        for change in changeset.recipechange_set.all().order_by('recipe__layerbranch'):
            fields = change.changed_fields(mapped=True)
            if fields:
                layerbranch = change.recipe.layerbranch
                layer = layerbranch.layer
                if last_layer != layer:
                    patchname = "%s.patch" % layer.name
                    patches.append(patchname)
                    layerfetchdir = os.path.join(fetchdir, layer.get_fetch_dir())
                    recipeparse.checkout_layer_branch(layerbranch, layerfetchdir)
                    layerdir = os.path.join(layerfetchdir, layerbranch.vcs_subdir)
                    config_data_copy = recipeparse.setup_layer(tinfoil.config_data, fetchdir, layerdir, layer, layerbranch)
                    if outfile:
                        outfile.close()
                    outfile = open(os.path.join(tmpoutdir, patchname), 'w')
                    last_layer = layer
                recipefile = str(os.path.join(layerfetchdir, layerbranch.vcs_subdir, change.recipe.filepath, change.recipe.filename))
                varlist = list(set(fields.keys() + meta_vars))
                varfiles = recipeparse.get_var_files(recipefile, varlist, config_data_copy)
                filevars = localise_file_vars(recipefile, varfiles, fields.keys())
                for f, fvars in filevars.items():
                    filefields = dict((k, fields[k]) for k in fvars)
                    patch = patch_recipe(f, layerfetchdir, filefields)
                    for line in patch:
                        outfile.write(line)
    finally:
        if outfile:
            outfile.close()

    # If we have more than one patch, tar it up, otherwise just return the single patch file
    ret = None
    if len(patches) > 1:
        (tmptarfd, tmptarname) = tempfile.mkstemp('.tar.gz', 'bulkchange-', outputdir)
        tmptarfile = os.fdopen(tmptarfd, "w")
        tar = tarfile.open(None, "w:gz", tmptarfile)
        for patch in patches:
            patchfn = os.path.join(tmpoutdir, patch)
            tar.add(patchfn)
        tar.close()
        ret = tmptarname
    elif len(patches) == 1:
        (tmppatchfd, tmppatchname) = tempfile.mkstemp('.patch', 'bulkchange-', outputdir)
        tmppatchfile = os.fdopen(tmppatchfd, "w")
        with open(os.path.join(tmpoutdir, patches[0]), "rb") as patchfile:
            shutil.copyfileobj(patchfile, tmppatchfile)
        tmppatchfile.close()
        ret = tmppatchname

    shutil.rmtree(tmpoutdir)
    return ret


def patch_recipe(fn, relpath, values):
    """Update or insert variable values into a recipe file.
       Note that some manual inspection/intervention may be required
       since this cannot handle all situations.
    """
    remainingnames = {}
    for k in values.keys():
        remainingnames[k] = recipe_progression.index(k) if k in recipe_progression else -1
    remainingnames = SortedDict(sorted(remainingnames.iteritems(), key=lambda x: x[1]))

    with tempfile.NamedTemporaryFile('w', delete=False) as tf:
        def outputvalue(name):
            rawtext = '%s = "%s"\n' % (name, values[name])
            if name in nowrap_vars:
                tf.write(rawtext)
            else:
                wrapped = textwrap.wrap(rawtext)
                for wrapline in wrapped[:-1]:
                    tf.write('%s \\\n' % wrapline)
                tf.write('%s\n' % wrapped[-1])

        tfn = tf.name
        with open(fn, 'r') as f:
            # First runthrough - find existing names (so we know not to insert based on recipe_progression)
            # Second runthrough - make the changes
            existingnames = []
            for runthrough in [1, 2]:
                currname = None
                for line in f:
                    if not currname:
                        insert = False
                        for k in remainingnames.keys():
                            for p in recipe_progression:
                                if line.startswith(p):
                                    if remainingnames[k] > -1 and recipe_progression.index(p) > remainingnames[k] and runthrough > 1 and not k in existingnames:
                                        outputvalue(k)
                                        del remainingnames[k]
                                    break
                        for k in remainingnames.keys():
                            if line.startswith(k):
                                currname = k
                                if runthrough == 1:
                                    existingnames.append(k)
                                else:
                                    del remainingnames[k]
                                break
                        if currname and runthrough > 1:
                            outputvalue(currname)

                    if currname:
                        sline = line.rstrip()
                        if not sline.endswith('\\'):
                            currname = None
                        continue
                    if runthrough > 1:
                        tf.write(line)
                f.seek(0)
        if remainingnames:
            tf.write('\n')
            for k in remainingnames.keys():
                outputvalue(k)

    fromlines = open(fn, 'U').readlines()
    tolines = open(tfn, 'U').readlines()
    relfn = os.path.relpath(fn, relpath)
    diff = difflib.unified_diff(fromlines, tolines, 'a/%s' % relfn, 'b/%s' % relfn)
    os.remove(tfn)
    return diff

def localise_file_vars(fn, varfiles, varlist):
    from collections import defaultdict

    fndir = os.path.dirname(fn) + os.sep

    first_meta_file = None
    for v in meta_vars:
        f = varfiles.get(v, None)
        if f:
            actualdir = os.path.dirname(f) + os.sep
            if actualdir.startswith(fndir):
                first_meta_file = f
                break

    filevars = defaultdict(list)
    for v in varlist:
        f = varfiles[v]
        # Only return files that are in the same directory as the recipe or in some directory below there
        # (this excludes bbclass files and common inc files that wouldn't be appropriate to set the variable
        # in if we were going to set a value specific to this recipe)
        if f:
            actualfile = f
        else:
            # Variable isn't in a file, if it's one of the "meta" vars, use the first file with a meta var in it
            if first_meta_file:
                actualfile = first_meta_file
            else:
                actualfile = fn

        actualdir = os.path.dirname(actualfile) + os.sep
        if not actualdir.startswith(fndir):
            actualfile = fn
        filevars[actualfile].append(v)

    return filevars

def get_changeset(pk):
    from layerindex.models import RecipeChangeset
    res = list(RecipeChangeset.objects.filter(pk=pk)[:1])
    if res:
        return res[0]
    return None

def usage():
    print("Usage: bulkchange.py <id> <outputdir>")

def main():
    if '--help' in sys.argv:
        usage()
        sys.exit(0)
    if len(sys.argv) < 3:
        usage()
        sys.exit(1)

    utils.setup_django()
    import settings

    branch = utils.get_branch('master')
    fetchdir = settings.LAYER_FETCH_DIR
    bitbakepath = os.path.join(fetchdir, 'bitbake')

    (tinfoil, tempdir) = recipeparse.init_parser(settings, branch, bitbakepath, True)

    changeset = get_changeset(sys.argv[1])
    if not changeset:
        sys.stderr.write("Unable to find changeset with id %s\n" % sys.argv[1])
        sys.exit(1)

    outp = generate_patches(tinfoil, fetchdir, changeset, sys.argv[2])
    if outp:
        print outp
    else:
        sys.stderr.write("No changes to write\n")
        sys.exit(1)

    shutil.rmtree(tempdir)
    sys.exit(0)


if __name__ == "__main__":
    main()
