# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0010_add_dependencies'),
    ]

    operations = [
        migrations.CreateModel(
            name='Maintainer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('email', models.CharField(max_length=255, blank=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Milestone',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=100)),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeDistro',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('distro', models.CharField(max_length=100, blank=True)),
                ('alias', models.CharField(max_length=100, blank=True)),
                ('recipe', models.ForeignKey(to='layerindex.Recipe')),
            ],
        ),
        migrations.CreateModel(
            name='RecipeMaintainer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeMaintainerHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('title', models.CharField(max_length=255, blank=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('sha1', models.CharField(max_length=64, unique=True)),
                ('author', models.ForeignKey(to='rrs.Maintainer')),
            ],
        ),
        migrations.CreateModel(
            name='RecipeUpgrade',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('sha1', models.CharField(max_length=40, blank=True)),
                ('title', models.CharField(max_length=1024, blank=True)),
                ('version', models.CharField(max_length=100, blank=True)),
                ('author_date', models.DateTimeField(db_index=True)),
                ('commit_date', models.DateTimeField(db_index=True)),
                ('maintainer', models.ForeignKey(blank=True, to='rrs.Maintainer')),
                ('recipe', models.ForeignKey(to='layerindex.Recipe')),
            ],
        ),
        migrations.CreateModel(
            name='RecipeUpstream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('version', models.CharField(max_length=100, blank=True)),
                ('type', models.CharField(max_length=1, blank=True, db_index=True, choices=[('A', 'Automatic'), ('M', 'Manual')])),
                ('status', models.CharField(max_length=1, blank=True, db_index=True, choices=[('A', 'All'), ('N', 'Not updated'), ('C', "Can't be updated"), ('Y', 'Up-to-date'), ('D', 'Downgrade'), ('U', 'Unknown')])),
                ('no_update_reason', models.CharField(max_length=255, blank=True, db_index=True)),
                ('date', models.DateTimeField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='RecipeUpstreamHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('start_date', models.DateTimeField(db_index=True)),
                ('end_date', models.DateTimeField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='Release',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(db_index=True)),
            ],
        ),
        migrations.AddField(
            model_name='recipeupstream',
            name='history',
            field=models.ForeignKey(to='rrs.RecipeUpstreamHistory'),
        ),
        migrations.AddField(
            model_name='recipeupstream',
            name='recipe',
            field=models.ForeignKey(to='layerindex.Recipe'),
        ),
        migrations.AddField(
            model_name='recipemaintainer',
            name='history',
            field=models.ForeignKey(to='rrs.RecipeMaintainerHistory'),
        ),
        migrations.AddField(
            model_name='recipemaintainer',
            name='maintainer',
            field=models.ForeignKey(to='rrs.Maintainer'),
        ),
        migrations.AddField(
            model_name='recipemaintainer',
            name='recipe',
            field=models.ForeignKey(to='layerindex.Recipe'),
        ),
        migrations.AddField(
            model_name='milestone',
            name='release',
            field=models.ForeignKey(to='rrs.Release'),
        ),
        migrations.AlterUniqueTogether(
            name='milestone',
            unique_together=set([('release', 'name')]),
        ),
    ]
