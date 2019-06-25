#!/bin/sh

# Script to be used on a regular basis to prevent requirements.txt
# from going stale
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

if [ ! -f requirements.txt ] ; then
    echo "No requirements.txt file, please run this in the right directory"
    exit 1
fi

set -e

tmpdir=`mktemp -d`
virtualenv -p python3 $tmpdir
. $tmpdir/bin/activate
pip install -r requirements.txt
newreqs="requirements.txt.updated"
echo "Creating $newreqs"
pip freeze > $newreqs
newreqsdiff="requirements.txt.diff"
echo "Creating $newreqsdiff"
diff -udN requirements.txt $newreqs > $newreqsdiff || true
outdated="outdated.txt"
echo "Creating $outdated"
pip list --outdated > $outdated
pip install pipdeptree
deptree="deptree.txt"
echo "Creating $deptree"
pipdeptree > $deptree
pip install safety
safety="safety_check.txt"
echo "Running safety check (output also to $safety)"
safety check | tee $safety
deactivate
rm -rf $tmpdir

