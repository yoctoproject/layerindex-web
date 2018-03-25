# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rrs', '0007_python23'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceplanlayerbranch',
            name='upgrade_date',
            field=models.DateTimeField(verbose_name='Recipe upgrade date', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='maintenanceplanlayerbranch',
            name='upgrade_rev',
            field=models.CharField(verbose_name='Recipe upgrade revision ', max_length=80, blank=True),
        ),
    ]
