# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0016_classicrecipe_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='classicrecipe',
            name='needs_attention',
            field=models.BooleanField(default=False),
        ),
    ]
