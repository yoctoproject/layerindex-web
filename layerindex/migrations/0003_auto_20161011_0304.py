# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0002_distro'),
    ]

    operations = [
        migrations.AddField(
            model_name='layerbranch',
            name='collection',
            field=models.CharField(max_length=40, help_text='Name of the layer that could be used in the list of dependencies - can only contain letters, numbers and dashes', verbose_name='Layer Collection', null=True),
        ),
        migrations.AddField(
            model_name='layerbranch',
            name='version',
            field=models.CharField(max_length=10, blank=True, help_text='The layer version for this particular branch.', verbose_name='Layer Version', null=True),
        ),
    ]
