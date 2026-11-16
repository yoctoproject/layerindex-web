# layerindex-web - fixtures shared between test modules
#
# Copyright (C) 2026 Qbee AS
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT
#
# AI-Generated: written with Claude Code

import datetime
import types

import pytest


@pytest.fixture
def seeded_index(db):
    """A small index with a row behind every REST API endpoint.

    It has two branches and a layer in each status:

    - openembedded-core, published, on both branches
    - meta-alpha, published, on both branches. On master it is indexed, is
      Yocto Project Compatible and depends on openembedded-core and on
      meta-pending; on the release branch it has not been parsed yet
    - meta-beta, published, on master only, recommends meta-alpha
    - meta-frozen, "No update", on master only
    - meta-pending, new (not published), on master only, with a machine and
      a recipe

    Nullable fields have both a value and NULL somewhere in the data.
    """
    # Imported here because tests/test_dockersetup.py also runs on a host
    # that has no Django, and pytest loads this file for it too
    from layerindex.models import (
        BBAppend, BBClass, Branch, Distro, DynamicBuildDep, IncFile,
        LayerBranch, LayerDependency, LayerItem, LayerMaintainer, LayerNote,
        Machine, PackageConfig, Patch, PythonEnvironment, Recipe,
        RecipeFileDependency, Source, StaticBuildDep, YPCompatibleVersion)

    def add_layer(name, status='P', layer_type='S'):
        return LayerItem.objects.create(
            name=name, status=status, layer_type=layer_type,
            summary='%s summary' % name, description='%s description' % name,
            vcs_url='https://git.example.com/%s' % name,
            vcs_web_url='https://git.example.com/web/%s' % name)

    def add_indexed(layer, branch, collection, **kwargs):
        """A layer branch as the update script leaves it after a successful parse"""
        return LayerBranch.objects.create(
            layer=layer, branch=branch, collection=collection, version='1',
            actual_branch=branch.name,
            vcs_last_fetch=datetime.datetime(2026, 10, 1, 12, 0, 0),
            vcs_last_rev='0123456789abcdef0123456789abcdef01234567',
            vcs_last_commit=datetime.datetime(2026, 9, 30, 8, 30, 0),
            **kwargs)

    env = PythonEnvironment.objects.create(name='Python 3', python_command='python3')
    # Created by migration 0001
    master, _ = Branch.objects.get_or_create(name='master', defaults={'bitbake_branch': 'master'})
    release = Branch.objects.create(name='scarthgap', bitbake_branch='2.8',
                                    short_description='Yocto Project 5.0',
                                    sort_priority=500, update_environment=env)

    core = add_layer('openembedded-core', layer_type='A')
    alpha = add_layer('meta-alpha')
    beta = add_layer('meta-beta')
    frozen = add_layer('meta-frozen', status='X')
    pending = add_layer('meta-pending', status='N', layer_type='B')

    compatible = YPCompatibleVersion.objects.create(
        name='5.0', description='Yocto Project Compatible 5.0',
        image_url='https://example.com/compatible.png',
        link_url='https://example.com/compatible')

    core_master = add_indexed(core, master, 'core', vcs_subdir='meta')
    core_release = add_indexed(core, release, 'core', vcs_subdir='meta')
    alpha_master = add_indexed(alpha, master, 'alpha', yp_compatible_version=compatible)
    alpha_release = LayerBranch.objects.create(layer=alpha, branch=release)
    beta_master = add_indexed(beta, master, 'beta')
    frozen_master = add_indexed(frozen, master, 'frozen')
    pending_master = add_indexed(pending, master, 'pending')

    LayerDependency.objects.create(layerbranch=alpha_master, dependency=core)
    LayerDependency.objects.create(layerbranch=alpha_master, dependency=pending)
    LayerDependency.objects.create(layerbranch=alpha_release, dependency=core)
    LayerDependency.objects.create(layerbranch=beta_master, dependency=core)
    LayerDependency.objects.create(layerbranch=beta_master, dependency=alpha, required=False)

    LayerMaintainer.objects.create(layerbranch=core_master, name='Carol Example',
                                   email='carol@example.com')
    LayerMaintainer.objects.create(layerbranch=alpha_master, name='Alice Example',
                                   email='alice@example.com')
    LayerMaintainer.objects.create(layerbranch=alpha_master, name='Bob Example',
                                   email='bob@example.com', status='I',
                                   responsibility='documentation')
    LayerMaintainer.objects.create(layerbranch=alpha_release, name='Alice Example',
                                   email='alice@example.com')

    LayerNote.objects.create(layer=alpha, text='Mirrored from an internal repository.')

    Recipe.objects.create(layerbranch=core_master, filename='base-example_2.0.bb',
                          filepath='recipes-core/base-example',
                          pn='base-example', pv='2.0')
    example = Recipe.objects.create(
        layerbranch=alpha_master, filename='example_1.0.bb',
        filepath='recipes-example/example', pn='example', pv='1.0', pr='r0',
        summary='An example', description='An example recipe',
        section='examples', license='MIT',
        homepage='https://example.com/example',
        bugtracker='https://example.com/example/issues',
        provides='example', bbclassextend='native',
        inherits='autotools pkgconfig')
    Recipe.objects.create(layerbranch=alpha_release, filename='example_0.9.bb',
                          filepath='recipes-example/example', pn='example', pv='0.9')
    Recipe.objects.create(layerbranch=pending_master, filename='pending-example_1.0.bb',
                          filepath='recipes-example/pending-example',
                          pn='pending-example', pv='1.0')

    Source.objects.create(recipe=example, url='https://example.com/example-1.0.tar.gz',
                          sha256sum='0' * 64)
    Source.objects.create(recipe=example, url='file://defconfig')
    Patch.objects.create(recipe=example, src_path='fix-build.patch',
                         path='recipes-example/example/files/fix-build.patch',
                         status='P', apply_order=1)
    Patch.objects.create(recipe=example, src_path='unused.patch',
                         path='recipes-example/example/files/unused.patch',
                         applied=False)
    ssl = PackageConfig.objects.create(recipe=example, feature='ssl',
                                       with_option='--with-ssl',
                                       without_option='--without-ssl',
                                       build_deps='openssl')
    openssl = DynamicBuildDep.objects.create(name='openssl')
    openssl.package_configs.add(ssl)
    openssl.recipes.add(example)
    StaticBuildDep.objects.create(name='zlib').recipes.add(example)
    RecipeFileDependency.objects.create(recipe=example, layerbranch=core_master,
                                        path='meta/classes-recipe/autotools.bbclass')

    Machine.objects.create(layerbranch=alpha_master, name='alpha-board',
                           description='Alpha reference board')
    Machine.objects.create(layerbranch=pending_master, name='pending-board',
                           description='Pending reference board')
    Distro.objects.create(layerbranch=alpha_master, name='alphaos',
                          description='Alpha OS')
    BBClass.objects.create(layerbranch=alpha_master, name='alpha-image',
                           bbclass_type='Recipe')
    BBAppend.objects.create(layerbranch=beta_master, filename='example_%.bbappend',
                            filepath='recipes-example/example')
    IncFile.objects.create(layerbranch=alpha_master,
                           path='recipes-example/example/example.inc')

    return types.SimpleNamespace(
        master=master, release=release,
        core=core, alpha=alpha, beta=beta, frozen=frozen, pending=pending,
        core_master=core_master, core_release=core_release,
        alpha_master=alpha_master, alpha_release=alpha_release,
        beta_master=beta_master, frozen_master=frozen_master,
        pending_master=pending_master, example=example)
