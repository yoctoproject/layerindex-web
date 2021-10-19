# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0010_add_dependencies'),
        ('rrs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenancePlan',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('updates_enabled', models.BooleanField(verbose_name='Enable updates', default=True, help_text='Enable automatically updating metadata for this plan via the update scripts')),
            ],
        ),
        migrations.CreateModel(
            name='MaintenancePlanLayerBranch',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('layerbranch', models.ForeignKey(to='layerindex.LayerBranch', on_delete=models.CASCADE)),
                ('plan', models.ForeignKey(to='rrs.MaintenancePlan', on_delete=models.CASCADE)),
            ],
            options={'verbose_name_plural': 'Maintenance plan layer branches'},
        ),
    ]
