# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0004_maint_plan_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='release',
            name='plan',
            field=models.ForeignKey(to='rrs.MaintenancePlan', on_delete=models.CASCADE),
        ),
    ]
