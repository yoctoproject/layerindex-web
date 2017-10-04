# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0008_yp_compatible'),
    ]

    operations = [
        migrations.AlterField(
            model_name='layerbranch',
            name='collection',
            field=models.CharField(help_text='Name of the collection that the layer provides for the purpose of expressing dependencies (as specified in BBFILE_COLLECTIONS). Can only contain letters, numbers and dashes.', max_length=40, blank=True, null=True, verbose_name='Layer Collection'),
        ),
    ]
