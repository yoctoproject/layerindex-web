#!/bin/sh

# Dump database without user tables (for the purpose of creating a dump
# that can be imported into a fresh database)
#
# Copyright (C) 2019 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

if [ "$1" = "" ] ; then
    echo "Please specify a database"
    exit 1
fi

if [ "$2" = "" ] ; then
    echo "Please specify an output file (.sql)"
    exit 1
fi

if [ -f $2 ] ; then
    echo "File $2 already exists"
    exit 1
fi

if [ -f $2.gz ] ; then
    echo "File $2.gz already exists"
    exit 1
fi

# This will ask for the password twice, not much we can really do about
# that though
# First, get the structure without data
mysqldump $1 -u root -p --no-data > $2
# Second, the data with a number of exclusions
mysqldump $1 -u root -p --no-create-info \
  --ignore-table=$1.auth_group \
  --ignore-table=$1.auth_group_permissions \
  --ignore-table=$1.auth_permission \
  --ignore-table=$1.auth_user \
  --ignore-table=$1.auth_user_groups \
  --ignore-table=$1.auth_user_user_permissions \
  --ignore-table=$1.layerindex_userprofile \
  --ignore-table=$1.layerindex_securityquestionanswer \
  --ignore-table=$1.layerindex_sitenotice \
  --ignore-table=$1.layerindex_layerupdate \
  --ignore-table=$1.layerindex_update \
  --ignore-table=$1.reversion_revision \
  --ignore-table=$1.reversion_version \
  --ignore-table=$1.rrs_maintainer \
  --ignore-table=$1.rrs_maintenanceplan \
  --ignore-table=$1.rrs_maintenanceplanlayerbranch \
  --ignore-table=$1.rrs_milestone \
  --ignore-table=$1.rrs_recipedistro \
  --ignore-table=$1.rrs_recipemaintainer \
  --ignore-table=$1.rrs_recipemaintainerhistory \
  --ignore-table=$1.rrs_recipemaintenancelink \
  --ignore-table=$1.rrs_recipeupgrade \
  --ignore-table=$1.rrs_recipeupstream \
  --ignore-table=$1.rrs_recipeupstreamhistory \
  --ignore-table=$1.rrs_release \
  --ignore-table=$1.django_session \
  --ignore-table=$1.django_admin_log \
  --ignore-table=$1.axes_accessattempt \
  --ignore-table=$1.axes_accesslog \
  >> $2
gzip $2
