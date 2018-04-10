# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0015_rmh_layerbranch_populate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recipemaintainerhistory',
            name='layerbranch',
            field=models.ForeignKey(to='layerindex.LayerBranch'),
        ),
    ]
