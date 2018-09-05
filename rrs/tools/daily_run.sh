#!/bin/bash

rrs_dir=__RRS_PATH__
venv_activate=__VENV_ACTIVATE__

source $venv_activate

$rrs_dir/layerindex/update.py
$rrs_dir/rrs/tools/rrs_maintainer_history.py -d
$rrs_dir/rrs/tools/rrs_upgrade_history.py -d
$rrs_dir/rrs/tools/rrs_upstream_history.py -d
$rrs_dir/rrs/tools/rrs_distros.py -d

if [ "$1" = "email" ]; then
	$rrs_dir/rrs/tools/rrs_upstream_email.py
fi
