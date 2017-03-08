# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0006_change_branch_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='layeritem',
            name='status',
            field=models.CharField(default='N', choices=[('N', 'New'), ('P', 'Published'), ('X', 'No update')], max_length=1),
        ),
    ]
