# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-06-21 05:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0027_patch_apply_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='hidden',
            field=models.BooleanField(default=False, help_text='Hide from normal selections', verbose_name='Hidden'),
        ),
    ]