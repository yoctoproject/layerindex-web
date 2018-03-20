# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from datetime import date


def insert_initial_data(apps, schema_editor):
    Maintainer = apps.get_model('rrs', 'Maintainer')
    Release = apps.get_model('rrs', 'Release')
    Milestone = apps.get_model('rrs', 'Milestone')

    m = Maintainer(name='No maintainer')
    m.save()
    m = Maintainer(name='All')
    m.save()
    release_1 = Release(name='1.0', start_date=date(2010, 6, 20), end_date=date(2011, 4, 1))
    release_1.save()
    release_2 = Release(name='1.1', start_date=date(2011, 4, 2), end_date=date(2011, 10, 3))
    release_2.save()
    release_3 = Release(name='1.2', start_date=date(2011, 10, 4), end_date=date(2012, 4, 27))
    release_3.save()
    release_4 = Release(name='1.3', start_date=date(2012, 4, 28), end_date=date(2012, 10, 26))
    release_4.save()
    release_5 = Release(name='1.4', start_date=date(2012, 10, 27), end_date=date(2013, 4, 26))
    release_5.save()
    release_6 = Release(name='1.5', start_date=date(2013, 4, 27), end_date=date(2013, 10, 18))
    release_6.save()
    release_7 = Release(name='1.6', start_date=date(2013, 10, 19), end_date=date(2014, 5, 25))
    release_7.save()
    release_8 = Release(name='1.7', start_date=date(2014, 5, 26), end_date=date(2014, 10, 31))
    release_8.save()
    release_9 = Release(name='1.8', start_date=date(2014, 11, 1), end_date=date(2015, 4, 24))
    release_9.save()
    release_10 = Release(name='2.0', start_date=date(2015, 4, 27), end_date=date(2015, 10, 30))
    release_10.save()
    release_11 = Release(name='2.1', start_date=date(2015, 11, 2), end_date=date(2016, 4, 29))
    release_11.save()
    release_12 = Release(name='2.2', start_date=date(2016, 5, 2), end_date=date(2016, 10, 28))
    release_12.save()
    release_13 = Release(name='2.3', start_date=date(2016, 10, 31), end_date=date(2017, 4, 30))
    release_13.save()
    release_14 = Release(name='2.4', start_date=date(2017, 5, 1), end_date=date(2017, 10, 20))
    release_14.save()
    release_15 = Release(name='2.5', start_date=date(2017, 10, 23), end_date=date(2018, 4, 27))
    release_15.save()
    milestone = Milestone(release=release_1, name='M1', start_date=date(2010, 6, 20), end_date=date(2010, 11, 7))
    milestone.save()
    milestone = Milestone(release=release_1, name='M2', start_date=date(2010, 11, 8), end_date=date(2010, 12, 10))
    milestone.save()
    milestone = Milestone(release=release_1, name='M3', start_date=date(2010, 12, 11), end_date=date(2011, 2, 4))
    milestone.save()
    milestone = Milestone(release=release_1, name='M4', start_date=date(2011, 2, 5), end_date=date(2011, 4, 1))
    milestone.save()
    milestone = Milestone(release=release_1, name='All', start_date=release_1.start_date, end_date=release_1.end_date)
    milestone.save()
    milestone = Milestone(release=release_2, name='M1', start_date=date(2011, 4, 2), end_date=date(2011, 5, 23))
    milestone.save()
    milestone = Milestone(release=release_2, name='M2', start_date=date(2011, 5, 24), end_date=date(2011, 7, 4))
    milestone.save()
    milestone = Milestone(release=release_2, name='M3', start_date=date(2011, 7, 5), end_date=date(2011, 7, 27))
    milestone.save()
    milestone = Milestone(release=release_2, name='M4', start_date=date(2011, 7, 28), end_date=date(2011, 10, 4))
    milestone.save()
    milestone = Milestone(release=release_2, name='All', start_date=release_2.start_date, end_date=release_2.end_date)
    milestone.save()
    milestone = Milestone(release=release_3, name='M1', start_date=date(2011, 10, 4), end_date=date(2011, 12, 2))
    milestone.save()
    milestone = Milestone(release=release_3, name='M2', start_date=date(2011, 12, 3), end_date=date(2012, 1, 6))
    milestone.save()
    milestone = Milestone(release=release_3, name='M3', start_date=date(2012, 1, 7), end_date=date(2012, 2, 24))
    milestone.save()
    milestone = Milestone(release=release_3, name='M4', start_date=date(2012, 2, 25), end_date=date(2012, 4, 27))
    milestone.save()
    milestone = Milestone(release=release_3, name='All', start_date=release_3.start_date, end_date=release_3.end_date)
    milestone.save()
    milestone = Milestone(release=release_4, name='M1', start_date=date(2012, 4, 28), end_date=date(2012, 6, 10))
    milestone.save()
    milestone = Milestone(release=release_4, name='M2', start_date=date(2012, 6, 11), end_date=date(2012, 7, 8))
    milestone.save()
    milestone = Milestone(release=release_4, name='M3', start_date=date(2012, 7, 9), end_date=date(2012, 8, 5))
    milestone.save()
    milestone = Milestone(release=release_4, name='M4', start_date=date(2012, 8, 6), end_date=date(2012, 9, 2))
    milestone.save()
    milestone = Milestone(release=release_4, name='M5', start_date=date(2012, 9, 3), end_date=date(2012, 10, 26))
    milestone.save()
    milestone = Milestone(release=release_4, name='All', start_date=release_4.start_date, end_date=release_4.end_date)
    milestone.save()
    milestone = Milestone(release=release_5, name='M1', start_date=date(2012, 10, 27), end_date=date(2012, 12, 14))
    milestone.save()
    milestone = Milestone(release=release_5, name='M2', start_date=date(2012, 12, 15), end_date=date(2013, 1, 11))
    milestone.save()
    milestone = Milestone(release=release_5, name='M3', start_date=date(2013, 1, 12), end_date=date(2013, 2, 8))
    milestone.save()
    milestone = Milestone(release=release_5, name='M4', start_date=date(2013, 2, 9), end_date=date(2013, 3, 8))
    milestone.save()
    milestone = Milestone(release=release_5, name='M5', start_date=date(2013, 3, 9), end_date=date(2013, 4, 5))
    milestone.save()
    milestone = Milestone(release=release_5, name='M6', start_date=date(2013, 4, 6), end_date=date(2013, 4, 26))
    milestone.save()
    milestone = Milestone(release=release_5, name='All', start_date=release_5.start_date, end_date=release_5.end_date)
    milestone.save()
    milestone = Milestone(release=release_6, name='M1', start_date=date(2013, 4, 27), end_date=date(2013, 6, 2))
    milestone.save()
    milestone = Milestone(release=release_6, name='M2', start_date=date(2013, 6, 3), end_date=date(2013, 6, 30))
    milestone.save()
    milestone = Milestone(release=release_6, name='M3', start_date=date(2013, 7, 1), end_date=date(2013, 7, 28))
    milestone.save()
    milestone = Milestone(release=release_6, name='M4', start_date=date(2013, 7, 29), end_date=date(2013, 8, 25))
    milestone.save()
    milestone = Milestone(release=release_6, name='M5', start_date=date(2013, 8, 26), end_date=date(2013, 10, 18))
    milestone.save()
    milestone = Milestone(release=release_6, name='All', start_date=release_6.start_date, end_date=release_6.end_date)
    milestone.save()
    milestone = Milestone(release=release_7, name='M1', start_date=date(2013, 10, 19), end_date=date(2013, 12, 20))
    milestone.save()
    milestone = Milestone(release=release_7, name='M2', start_date=date(2013, 12, 21), end_date=date(2014, 1, 31))
    milestone.save()
    milestone = Milestone(release=release_7, name='M3', start_date=date(2014, 2, 1), end_date=date(2014, 2, 28))
    milestone.save()
    milestone = Milestone(release=release_7, name='M4', start_date=date(2014, 3, 1), end_date=date(2014, 3, 28))
    milestone.save()
    milestone = Milestone(release=release_7, name='M5', start_date=date(2014, 3, 29), end_date=date(2014, 5, 25))
    milestone.save()
    milestone = Milestone(release=release_7, name='All', start_date=release_7.start_date, end_date=release_7.end_date)
    milestone.save()
    milestone = Milestone(release=release_8, name='M1', start_date=date(2014, 5, 26), end_date=date(2014, 6, 20))
    milestone.save()
    milestone = Milestone(release=release_8, name='M2', start_date=date(2014, 6, 21), end_date=date(2014, 7, 25))
    milestone.save()
    milestone = Milestone(release=release_8, name='M3', start_date=date(2014, 7, 25), end_date=date(2014, 8, 29))
    milestone.save()
    milestone = Milestone(release=release_8, name='M4', start_date=date(2014, 8, 30), end_date=date(2014, 10, 31))
    milestone.save()
    milestone = Milestone(release=release_8, name='All', start_date=release_8.start_date, end_date=release_8.end_date)
    milestone.save()
    milestone = Milestone(release=release_9, name='M1', start_date=date(2014, 11, 1), end_date=date(2014, 12, 2))
    milestone.save()
    milestone = Milestone(release=release_9, name='M2', start_date=date(2014, 12, 3), end_date=date(2015, 1, 13))
    milestone.save()
    milestone = Milestone(release=release_9, name='M3', start_date=date(2015, 1, 14), end_date=date(2015, 2, 18))
    milestone.save()
    milestone = Milestone(release=release_9, name='M4', start_date=date(2015, 2, 19), end_date=date(2015, 4, 24))
    milestone.save()
    milestone = Milestone(release=release_9, name='All', start_date=release_9.start_date, end_date=release_9.end_date)
    milestone.save()
    milestone = Milestone(release=release_10, name='M1', start_date=date(2015, 4, 27), end_date=date(2015, 6, 21))
    milestone.save()
    milestone = Milestone(release=release_10, name='M2', start_date=date(2015, 6, 22), end_date=date(2015, 7, 26))
    milestone.save()
    milestone = Milestone(release=release_10, name='M3', start_date=date(2015, 7, 27), end_date=date(2015, 8, 23))
    milestone.save()
    milestone = Milestone(release=release_10, name='M4', start_date=date(2015, 8, 24), end_date=date(2015, 10, 30))
    milestone.save()
    milestone = Milestone(release=release_10, name='All', start_date=release_10.start_date, end_date=release_10.end_date)
    milestone.save()
    milestone = Milestone(release=release_11, name='M1', start_date=date(2015, 11, 2), end_date=date(2015, 12, 6))
    milestone.save()
    milestone = Milestone(release=release_11, name='M2', start_date=date(2015, 12, 7), end_date=date(2016, 1, 24))
    milestone.save()
    milestone = Milestone(release=release_11, name='M3', start_date=date(2016, 1, 25), end_date=date(2016, 2, 28))
    milestone.save()
    milestone = Milestone(release=release_11, name='M4', start_date=date(2016, 2, 29), end_date=date(2016, 4, 29))
    milestone.save()
    milestone = Milestone(release=release_11, name='All', start_date=release_11.start_date, end_date=release_11.end_date)
    milestone.save()
    milestone = Milestone(release=release_12, name='M1', start_date=date(2016, 5, 2), end_date=date(2016, 6, 12))
    milestone.save()
    milestone = Milestone(release=release_12, name='M2', start_date=date(2016, 6, 13), end_date=date(2016, 7, 17))
    milestone.save()
    milestone = Milestone(release=release_12, name='M3', start_date=date(2016, 7, 18), end_date=date(2016, 8, 28))
    milestone.save()
    milestone = Milestone(release=release_12, name='M4', start_date=date(2016, 8, 29), end_date=date(2016, 10, 28))
    milestone.save()
    milestone = Milestone(release=release_12, name='All', start_date=release_12.start_date, end_date=release_12.end_date)
    milestone.save()
    milestone = Milestone(release=release_13, name='M1', start_date=date(2016, 10, 31), end_date=date(2016, 12, 11))
    milestone.save()
    milestone = Milestone(release=release_13, name='M2', start_date=date(2016, 12, 12), end_date=date(2017, 1, 22))
    milestone.save()
    milestone = Milestone(release=release_13, name='M3', start_date=date(2017, 1, 23), end_date=date(2017, 2, 26))
    milestone.save()
    milestone = Milestone(release=release_13, name='M4', start_date=date(2017, 2, 27), end_date=date(2017, 4, 30))
    milestone.save()
    milestone = Milestone(release=release_13, name='All', start_date=release_13.start_date, end_date=release_13.end_date)
    milestone.save()
    milestone = Milestone(release=release_14, name='M1', start_date=date(2017, 5, 1), end_date=date(2017, 6, 11))
    milestone.save()
    milestone = Milestone(release=release_14, name='M2', start_date=date(2017, 6, 12), end_date=date(2017, 7, 16))
    milestone.save()
    milestone = Milestone(release=release_14, name='M3', start_date=date(2017, 7, 17), end_date=date(2017, 8, 20))
    milestone.save()
    milestone = Milestone(release=release_14, name='M4', start_date=date(2017, 8, 21), end_date=date(2017, 10, 20))
    milestone.save()
    milestone = Milestone(release=release_14, name='All', start_date=release_14.start_date, end_date=release_14.end_date)
    milestone.save()
    milestone = Milestone(release=release_15, name='M1', start_date=date(2017, 10, 23), end_date=date(2017, 12, 21))
    milestone.save()
    milestone = Milestone(release=release_15, name='M2', start_date=date(2017, 12, 22), end_date=date(2018, 1, 31))
    milestone.save()
    milestone = Milestone(release=release_15, name='M3', start_date=date(2018, 2, 1), end_date=date(2018, 3, 16))
    milestone.save()
    milestone = Milestone(release=release_15, name='M4', start_date=date(2018, 3, 17), end_date=date(2018, 4, 27))
    milestone.save()
    milestone = Milestone(release=release_15, name='All', start_date=release_15.start_date, end_date=release_15.end_date)
    milestone.save()


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
        migrations.RunPython(insert_initial_data),
    ]
