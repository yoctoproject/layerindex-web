# layerindex-web - tests for update script
#
# Copyright (C) 2018 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

# NOTE: requires pytest-django. Run using "pytest" from the root
# of the repository (add -s to avoid suppressing the output of commands
# when working on the tests)

# NOTE: for these tests to work with MySQL / MariaDB and Django 1.11, you will need
# to set the transaction isolation mode to READ COMMITTED (basically set
# transaction-isolation = READ-COMMITTED in the [mysqld] section of /etc/my.cnf)

# NOTE: we cannot practically save and restore the database between tests (since
# we want these tests to work with any database backend) nor use transactions
# (since we need to launch the update script which uses a separate database
# connection), thus these tests cannot depend upon eachother - i.e. they must
# not touch the test layer(s) in a manner that would affect any other test. In
# practice that means separate recipes for each test.

import sys
import os
import shutil
import subprocess
import pytest

basepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def run_cmd(cmd, cwd=None):
    if not cwd:
        cwd = basepath
    subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True, cwd=cwd)

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass

@pytest.fixture
def db_access_without_rollback_and_truncate(request, django_db_setup, django_db_blocker):
    django_db_blocker.unblock()
    request.addfinalizer(django_db_blocker.restore)

@pytest.fixture(scope="module")
def backup_settings(tmpdir_factory):
    stmpdir = tmpdir_factory.mktemp('settings')
    settingsfile = os.path.join(basepath, 'settings.py')
    backupfile = os.path.join(stmpdir, 'settings.bak')
    shutil.copy(settingsfile, backupfile)
    yield settingsfile
    shutil.copy(backupfile, settingsfile)

@pytest.fixture(scope="module")
def hack_settings(backup_settings):
    # It's horrific to have to do this, but we need to have additional
    # scripts connect to the testing database and not whatever's in settings.py
    # on disk right now, and this appears to be the only real way to do that
    from django.conf import settings
    with open(backup_settings, 'a') as f:
        f.write('\nDATABASES = %s\n' % settings.DATABASES)

@pytest.fixture(scope="module")
def import_layer(hack_settings):
    run_cmd("layerindex/tools/import_layer.py git://git.openembedded.org/openembedded-core -s meta openembedded-core")
    run_cmd("layerindex/tools/import_layer.py git://git.yoctoproject.org/meta-layerindex-test -s meta-layerindex-test")
    run_cmd("layerindex/update.py -l meta-layerindex-test")

def test_example_recipe(import_layer):
    from layerindex.models import Branch, LayerItem, LayerBranch
    layer = LayerItem.objects.get(name='meta-layerindex-test')
    layerbranch = LayerBranch.objects.get(layer__name='meta-layerindex-test')
    found = False
    for recipe in layerbranch.recipe_set.all():
        if recipe.pn == 'example':
            if found:
                assert False, 'Duplicate example recipe in database'
            assert recipe.pv == '0.1'
            assert recipe.summary == 'Example recipe'
            assert recipe.description == 'An example recipe used to test the OE layer index update script'
            assert recipe.license == 'MIT'
            assert recipe.filename == 'example_0.1.bb'
            assert recipe.filepath == 'recipes-example/example'
            # section is currently relying on what's set by bitbake.conf
            assert recipe.section == 'base'
            assert recipe.provides.split() == ['example']
            assert recipe.blacklisted == ''
            # homepage bugtracker bbclassextend inherits
            # dependencies
            found = True
    if not found:
        assert False, "Expected 'example' recipe not in database"

@pytest.fixture()
def repo(db_access_without_rollback_and_truncate):
    from layerindex.models import LayerItem
    from django.conf import settings
    fetchdir = settings.LAYER_FETCH_DIR
    layer = LayerItem.objects.get(name='meta-layerindex-test')
    urldir = layer.get_fetch_dir()
    repodir = os.path.join(fetchdir, urldir)
    yield repodir

def test_move_recipe_out(import_layer, repo, db_access_without_rollback_and_truncate):
    from layerindex.models import LayerBranch, Recipe
    layerbranch = LayerBranch.objects.get(layer__name='meta-layerindex-test')
    recipe = layerbranch.recipe_set.filter(pn='moveme').first()
    assert recipe, 'No moveme recipe found'
    os.makedirs(os.path.join(repo, 'meta-layerindex-othertest/recipes-somethingelse/moveme'))
    run_cmd('tree', cwd=repo)
    run_cmd('git mv meta-layerindex-test/recipes-example/moveme/moveme_0.1.bb meta-layerindex-othertest/recipes-somethingelse/moveme/moveme_0.1.bb', cwd=repo)
    run_cmd('git commit -m "Move recipe to a different layer"', cwd=repo)
    run_cmd("layerindex/update.py -d -l meta-layerindex-test --nofetch --nocheckout")
    # Recipe should have been deleted by update script
    with pytest.raises(Recipe.DoesNotExist):
        recipe.refresh_from_db()

def test_delete_recipe(import_layer, repo, db_access_without_rollback_and_truncate):
    from layerindex.models import LayerBranch, Recipe
    layerbranch = LayerBranch.objects.get(layer__name='meta-layerindex-test')
    recipe = layerbranch.recipe_set.filter(pn='deleteme').first()
    assert recipe, 'No deleteme recipe found'
    run_cmd('git rm meta-layerindex-test/recipes-example/deleteme/deleteme_0.1.bb', cwd=repo)
    run_cmd('git commit -m "Delete recipe"', cwd=repo)
    run_cmd("layerindex/update.py -d -l meta-layerindex-test --nofetch --nocheckout")
    # Recipe should have been deleted by update script
    with pytest.raises(Recipe.DoesNotExist):
        recipe.refresh_from_db()

def test_upgrade_recipe(import_layer, repo, db_access_without_rollback_and_truncate):
    # FIXME this test is a little simplistic
    from layerindex.models import LayerBranch, Recipe
    layerbranch = LayerBranch.objects.get(layer__name='meta-layerindex-test')
    recipe = Recipe.objects.filter(layerbranch=layerbranch, pn='upgrademe').first()
    assert recipe, 'No upgrademe recipe found'
    oldid = recipe.id
    run_cmd('git mv meta-layerindex-test/recipes-example/upgrademe/upgrademe_0.1.bb meta-layerindex-test/recipes-example/upgrademe/upgrademe_0.2.bb', cwd=repo)
    run_cmd('git commit -m "Upgrade recipe"', cwd=repo)
    run_cmd("layerindex/update.py -d -l meta-layerindex-test --nofetch --nocheckout")
    recipe = Recipe.objects.filter(layerbranch=layerbranch, pn='upgrademe').first()
    assert recipe.id == oldid
    assert recipe.pv == "0.2"
    assert recipe.filename == 'upgrademe_0.2.bb'
    assert recipe.filepath == 'recipes-example/upgrademe'

def test_add_recipe(import_layer, repo, db_access_without_rollback_and_truncate):
    from layerindex.models import LayerBranch, Recipe
    layerbranch = LayerBranch.objects.get(layer__name='meta-layerindex-test')
    recipe = Recipe.objects.filter(layerbranch=layerbranch, pn='addme').first()
    assert not recipe, 'addme recipe found when it should not have been'
    os.makedirs(os.path.join(repo, 'meta-layerindex-test/recipes-example/addme'))
    with open(os.path.join(repo, 'meta-layerindex-test/recipes-example/addme/addme_0.5.bb'), 'w') as f:
        f.write('SUMMARY = "Brand new recipe"\n')
        f.write('LICENSE = "MIT"\n')
    run_cmd('git add meta-layerindex-test/recipes-example/addme/addme_0.5.bb', cwd=repo)
    run_cmd('git commit -m "Add recipe"', cwd=repo)
    run_cmd("layerindex/update.py -d -l meta-layerindex-test --nofetch --nocheckout")
    # Recipe should have been deleted by update script
    recipe = Recipe.objects.filter(layerbranch=layerbranch, pn='addme').first()
    assert recipe, 'addme recipe not found'
    assert recipe.pv == "0.5"
    assert recipe.summary == "Brand new recipe"
    assert recipe.license == "MIT"



# FIXME test recipe modify
# FIXME test recipe upgrade with inc merge?
# FIXME test patches
# FIXME test sources
# FIXME test inherits

# FIXME test distro add
# FIXME test distro rename
# FIXME test distro modify
# FIXME test distro delete

# FIXME test machine add
# FIXME test machine rename
# FIXME test machine modify
# FIXME test machine delete

# FIXME test bbappend add
# FIXME test bbappend rename
# FIXME test bbappend delete

# FIXME test bbclass add
# FIXME test bbclass rename
# FIXME test bbclass delete

# FIXME test modify bbclass updates dependent recipes
# FIXME test modify inc updates dependent recipes

# FIXME 'adding' a group of layers 'out of order' e.g. layer1 - require layer 5 and 4..  layer 2 - require layer 3 and 4, layer 3 - require layer 5, layer 4 require layer 5, layer 5 (no requirements)

# FIXME test REST API (different module!)
