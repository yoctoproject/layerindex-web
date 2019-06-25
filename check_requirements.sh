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

if [ "$1" = "-q" ] ; then
    quiet="1"
elif [ "$1" = "" ] ; then
    quiet="0"
else
    echo "Invalid option: $1"
    exit 1
fi

vecho()
{
    if [ "$quiet" = "0" ] ; then
        echo "$@"
    fi
}


tmpdir=`mktemp -d`
vecho "Setting up virtual environment"
virtualenv -q -p python3 $tmpdir
. $tmpdir/bin/activate
pip install -q -r requirements.txt
newreqs="requirements.txt.updated"
vecho "Creating $newreqs"
pip freeze > $newreqs
newreqsdiff="requirements.txt.diff"
vecho "Creating $newreqsdiff"
diff -udN requirements.txt $newreqs > $newreqsdiff || true
outdated="outdated.txt"
vecho "Creating $outdated"
pip list --outdated > $outdated
pip install -q pipdeptree
deptree="deptree.txt"
vecho "Creating $deptree"
pipdeptree > $deptree
pip install -q safety
safety="safety_check.txt"
vecho "Running safety check (output also to $safety)"
safety check | tee $safety
echo
echo "Outdated components:"
echo
cat $outdated
deactivate
rm -rf $tmpdir

