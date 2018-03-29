# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0010_add_dependencies'),
        ('rrs', '0008_upgrade_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipemaintainerhistory',
            name='layerbranch',
            field=models.ForeignKey(blank=True, null=True, to='layerindex.LayerBranch'),
        ),
    ]
