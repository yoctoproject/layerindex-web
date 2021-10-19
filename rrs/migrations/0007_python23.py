# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0010_add_dependencies'),
        ('rrs', '0006_maintplan_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceplanlayerbranch',
            name='python2_environment',
            field=models.ForeignKey(blank=True, null=True, help_text='Environment to use for Python 2 commits', related_name='maintplan_layerbranch_python2_set', to='layerindex.PythonEnvironment', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='maintenanceplanlayerbranch',
            name='python3_environment',
            field=models.ForeignKey(blank=True, null=True, help_text='Environment to use for Python 3 commits', related_name='maintplan_layerbranch_python3_set', to='layerindex.PythonEnvironment', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='maintenanceplanlayerbranch',
            name='python3_switch_date',
            field=models.DateTimeField(verbose_name='Commit date to switch to Python 3', default=datetime.datetime(2016, 6, 2, 0, 0)),
        ),
    ]
