# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0009_layerbranch_collection'),
    ]

    operations = [
        migrations.CreateModel(
            name='DynamicBuildDep',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='PackageConfig',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('feature', models.CharField(max_length=255)),
                ('with_option', models.CharField(max_length=255, blank=True)),
                ('without_option', models.CharField(max_length=255, blank=True)),
                ('build_deps', models.CharField(max_length=255, blank=True)),
                ('recipe', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Recipe')),
            ],
        ),
        migrations.CreateModel(
            name='StaticBuildDep',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=255)),
                ('recipes', models.ManyToManyField(to='layerindex.Recipe')),
            ],
        ),
        migrations.AddField(
            model_name='dynamicbuilddep',
            name='package_configs',
            field=models.ManyToManyField(to='layerindex.PackageConfig'),
        ),
        migrations.AddField(
            model_name='dynamicbuilddep',
            name='recipes',
            field=models.ManyToManyField(to='layerindex.Recipe'),
        ),
    ]
