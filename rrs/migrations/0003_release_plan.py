# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0002_maintenanceplan'),
    ]

    operations = [
        migrations.AddField(
            model_name='release',
            name='plan',
            field=models.ForeignKey(null=True, to='rrs.MaintenancePlan', on_delete=models.CASCADE),
        ),
    ]
