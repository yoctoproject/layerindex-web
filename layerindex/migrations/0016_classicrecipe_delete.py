# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0015_comparison'),
    ]

    operations = [
        migrations.AddField(
            model_name='classicrecipe',
            name='deleted',
            field=models.BooleanField(default=False),
        ),
    ]
