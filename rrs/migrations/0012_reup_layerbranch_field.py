# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0011_release_name_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipeupstreamhistory',
            name='layerbranch',
            field=models.ForeignKey(null=True, to='layerindex.LayerBranch', on_delete=models.CASCADE),
        ),
    ]
