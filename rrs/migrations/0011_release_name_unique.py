# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0010_recipemaintenancelink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='release',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterUniqueTogether(
            name='release',
            unique_together=set([('plan', 'name')]),
        ),
    ]
