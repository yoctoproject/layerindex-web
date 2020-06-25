# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0004_layerdependency_required'),
    ]

    operations = [
        migrations.CreateModel(
            name='LayerUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started', models.DateTimeField()),
                ('finished', models.DateTimeField()),
                ('errors', models.IntegerField(default=0)),
                ('warnings', models.IntegerField(default=0)),
                ('log', models.TextField(blank=True)),
                ('layerbranch', models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.LayerBranch')),
            ],
        ),
        migrations.CreateModel(
            name='Update',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started', models.DateTimeField()),
                ('finished', models.DateTimeField(null=True, blank=True)),
                ('log', models.TextField(blank=True)),
                ('reload', models.BooleanField(help_text='Was this update a reload?', verbose_name='Reloaded', default=False)),
            ],
        ),
        migrations.AlterField(
            model_name='branch',
            name='name',
            field=models.CharField(max_length=50, verbose_name='Branch name'),
        ),
        migrations.AddField(
            model_name='layerupdate',
            name='update',
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to='layerindex.Update'),
        ),
    ]
