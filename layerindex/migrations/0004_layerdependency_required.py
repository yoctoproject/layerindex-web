# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0003_auto_20161011_0304'),
    ]

    operations = [
        migrations.AddField(
            model_name='layerdependency',
            name='required',
            field=models.BooleanField(default=True),
        ),
    ]
