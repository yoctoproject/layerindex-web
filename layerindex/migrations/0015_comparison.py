# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0014_sitenotice'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='comparison',
            field=models.BooleanField(default=False, help_text='If enabled, branch is for comparison purposes only and will appear separately', verbose_name='Comparison'),
        ),
        migrations.AlterField(
            model_name='classicrecipe',
            name='cover_status',
            field=models.CharField(default='U', choices=[('U', 'Unknown'), ('N', 'Not available'), ('R', 'Replaced'), ('P', 'Provided (BBCLASSEXTEND)'), ('C', 'Provided (PACKAGECONFIG)'), ('S', 'Distro-specific'), ('O', 'Obsolete'), ('E', 'Equivalent functionality'), ('D', 'Direct match')], max_length=1),
        ),
    ]
