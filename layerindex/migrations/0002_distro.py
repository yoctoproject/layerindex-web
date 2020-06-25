# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Distro',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('layerbranch', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch')),
            ],
        ),
    ]
