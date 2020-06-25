# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


def create_master_branch(apps, schema_editor):
    """Create an initial master branch, since the app expects it to exist"""
    Branch = apps.get_model('layerindex', 'Branch')
    master_branch = Branch()
    master_branch.name = 'master'
    master_branch.bitbake_branch = 'master'
    master_branch.save()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BBAppend',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('filename', models.CharField(max_length=255)),
                ('filepath', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'verbose_name': 'Append',
            },
        ),
        migrations.CreateModel(
            name='BBClass',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name': 'Class',
                'verbose_name_plural': 'Classes',
            },
        ),
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=50)),
                ('bitbake_branch', models.CharField(max_length=50)),
                ('short_description', models.CharField(blank=True, max_length=50)),
                ('sort_priority', models.IntegerField(blank=True, null=True)),
                ('updates_enabled', models.BooleanField(verbose_name='Enable updates', help_text='Enable automatically updating layer metadata for this branch via the update script', default=True)),
                ('updated', models.DateTimeField(null=True, auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Branches',
            },
        ),
        migrations.CreateModel(
            name='LayerBranch',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('vcs_subdir', models.CharField(verbose_name='Repository subdirectory', blank=True, help_text='Subdirectory within the repository where the layer is located, if not in the root (usually only used if the repository contains more than one layer)', max_length=40)),
                ('vcs_last_fetch', models.DateTimeField(verbose_name='Last successful fetch', blank=True, null=True)),
                ('vcs_last_rev', models.CharField(verbose_name='Last revision fetched', blank=True, max_length=80)),
                ('vcs_last_commit', models.DateTimeField(verbose_name='Last commit date', blank=True, null=True)),
                ('actual_branch', models.CharField(verbose_name='Actual Branch', blank=True, help_text='Name of the actual branch in the repository matching the core branch', max_length=80)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Branch')),
            ],
            options={
                'verbose_name_plural': 'Layer branches',
            },
        ),
        migrations.CreateModel(
            name='LayerDependency',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
            ],
            options={
                'verbose_name_plural': 'Layer dependencies',
            },
        ),
        migrations.CreateModel(
            name='LayerItem',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(verbose_name='Layer name', help_text='Name of the layer - must be unique and can only contain letters, numbers and dashes', max_length=40, unique=True)),
                ('status', models.CharField(default='N', max_length=1, choices=[('N', 'New'), ('P', 'Published')])),
                ('layer_type', models.CharField(max_length=1, choices=[('A', 'Base'), ('B', 'Machine (BSP)'), ('S', 'Software'), ('D', 'Distribution'), ('M', 'Miscellaneous')])),
                ('summary', models.CharField(help_text='One-line description of the layer', max_length=200)),
                ('description', models.TextField()),
                ('vcs_url', models.CharField(verbose_name='Repository URL', help_text='Fetch/clone URL of the repository', max_length=255)),
                ('vcs_web_url', models.URLField(verbose_name='Repository web interface URL', blank=True, help_text='URL of the web interface for browsing the repository, if any')),
                ('vcs_web_tree_base_url', models.CharField(verbose_name='Repository web interface tree base URL', blank=True, help_text='Base URL for the web interface for browsing directories within the repository, if any', max_length=255)),
                ('vcs_web_file_base_url', models.CharField(verbose_name='Repository web interface file base URL', blank=True, help_text='Base URL for the web interface for viewing files (blobs) within the repository, if any', max_length=255)),
                ('usage_url', models.CharField(verbose_name='Usage web page URL', blank=True, help_text='URL of a web page with more information about the layer and how to use it, if any (or path to file within repository)', max_length=255)),
                ('mailing_list_url', models.URLField(verbose_name='Mailing list URL', blank=True, help_text='URL of the info page for a mailing list for discussing the layer, if any')),
                ('index_preference', models.IntegerField(verbose_name='Preference', help_text='Number used to find preferred recipes in recipe search results (higher number is greater preference)', default=0)),
                ('classic', models.BooleanField(verbose_name='Classic', help_text='Is this OE-Classic?', default=False)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Layer',
                'permissions': (('publish_layer', 'Can publish layers'),),
            },
        ),
        migrations.CreateModel(
            name='LayerMaintainer',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('email', models.CharField(max_length=255)),
                ('responsibility', models.CharField(blank=True, help_text='Specific area(s) this maintainer is responsible for, if not the entire layer', max_length=200)),
                ('status', models.CharField(default='A', max_length=1, choices=[('A', 'Active'), ('I', 'Inactive')])),
                ('layerbranch', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch')),
            ],
        ),
        migrations.CreateModel(
            name='LayerNote',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('text', models.TextField()),
                ('layer', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerItem')),
            ],
        ),
        migrations.CreateModel(
            name='Machine',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('layerbranch', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch')),
            ],
        ),
        migrations.CreateModel(
            name='PythonEnvironment',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=50)),
                ('python_command', models.CharField(max_length=255, default='python')),
                ('virtualenv_path', models.CharField(blank=True, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('filename', models.CharField(max_length=255)),
                ('filepath', models.CharField(blank=True, max_length=255)),
                ('pn', models.CharField(blank=True, max_length=100)),
                ('pv', models.CharField(blank=True, max_length=100)),
                ('summary', models.CharField(blank=True, max_length=200)),
                ('description', models.TextField(blank=True)),
                ('section', models.CharField(blank=True, max_length=100)),
                ('license', models.CharField(blank=True, max_length=2048)),
                ('homepage', models.URLField(blank=True)),
                ('bugtracker', models.URLField(blank=True)),
                ('provides', models.CharField(blank=True, max_length=2048)),
                ('bbclassextend', models.CharField(blank=True, max_length=100)),
                ('inherits', models.CharField(blank=True, max_length=255)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('blacklisted', models.CharField(blank=True, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeChange',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('summary', models.CharField(blank=True, max_length=100)),
                ('description', models.TextField(blank=True)),
                ('section', models.CharField(blank=True, max_length=100)),
                ('license', models.CharField(blank=True, max_length=100)),
                ('homepage', models.URLField(verbose_name='Homepage URL', blank=True)),
                ('bugtracker', models.URLField(verbose_name='Bug tracker URL', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeChangeset',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeFileDependency',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('path', models.CharField(db_index=True, max_length=255)),
                ('layerbranch', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='layerindex.LayerBranch')),
            ],
            options={
                'verbose_name_plural': 'Recipe file dependencies',
            },
        ),
        migrations.CreateModel(
            name='ClassicRecipe',
            fields=[
                ('recipe_ptr', models.OneToOneField(on_delete=models.deletion.CASCADE, primary_key=True, to='layerindex.Recipe', auto_created=True, parent_link=True, serialize=False)),
                ('cover_pn', models.CharField(verbose_name='Covering recipe', blank=True, max_length=100)),
                ('cover_status', models.CharField(default='U', max_length=1, choices=[('U', 'Unknown'), ('N', 'Not available'), ('R', 'Replaced'), ('P', 'Provided (BBCLASSEXTEND)'), ('C', 'Provided (PACKAGECONFIG)'), ('O', 'Obsolete'), ('E', 'Equivalent functionality'), ('D', 'Direct match')])),
                ('cover_verified', models.BooleanField(default=False)),
                ('cover_comment', models.TextField(blank=True)),
                ('classic_category', models.CharField(verbose_name='OE-Classic Category', blank=True, max_length=100)),
            ],
            options={
                'permissions': (('edit_classic', 'Can edit OE-Classic recipes'),),
            },
            bases=('layerindex.recipe',),
        ),
        migrations.AddField(
            model_name='recipefiledependency',
            name='recipe',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Recipe'),
        ),
        migrations.AddField(
            model_name='recipechange',
            name='changeset',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.RecipeChangeset'),
        ),
        migrations.AddField(
            model_name='recipechange',
            name='recipe',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='+', to='layerindex.Recipe'),
        ),
        migrations.AddField(
            model_name='recipe',
            name='layerbranch',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch'),
        ),
        migrations.AddField(
            model_name='layerdependency',
            name='dependency',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='dependents_set', to='layerindex.LayerItem'),
        ),
        migrations.AddField(
            model_name='layerdependency',
            name='layerbranch',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='dependencies_set', to='layerindex.LayerBranch'),
        ),
        migrations.AddField(
            model_name='layerbranch',
            name='layer',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerItem'),
        ),
        migrations.AddField(
            model_name='branch',
            name='update_environment',
            field=models.ForeignKey(to='layerindex.PythonEnvironment', blank=True, null=True, on_delete=models.deletion.SET_NULL),
        ),
        migrations.AddField(
            model_name='bbclass',
            name='layerbranch',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch'),
        ),
        migrations.AddField(
            model_name='bbappend',
            name='layerbranch',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch'),
        ),
        migrations.AddField(
            model_name='classicrecipe',
            name='cover_layerbranch',
            field=models.ForeignKey(to='layerindex.LayerBranch', verbose_name='Covering layer', blank=True, null=True, on_delete=models.deletion.SET_NULL),
        ),
        migrations.RunPython(create_master_branch, reverse_code=migrations.RunPython.noop),
    ]
