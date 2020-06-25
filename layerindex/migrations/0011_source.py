# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0010_add_dependencies'),
    ]

    operations = [
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('url', models.CharField(max_length=255)),
                ('recipe', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Recipe')),
            ],
        ),
    ]
