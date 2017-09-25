# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('layerindex', '0007_layeritem_status_noupdate'),
    ]

    operations = [
        migrations.CreateModel(
            name='YPCompatibleVersion',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(help_text='Name of this Yocto Project compatible version (e.g. "2.0")', verbose_name='Yocto Project Version', max_length=25, unique=True)),
                ('description', models.TextField(blank=True)),
                ('image_url', models.CharField(blank=True, verbose_name='Image URL', max_length=300)),
                ('link_url', models.CharField(blank=True, verbose_name='Link URL', max_length=100)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name': 'Yocto Project Compatible version',
            },
        ),
        migrations.AlterModelOptions(
            name='layerbranch',
            options={'verbose_name_plural': 'Layer branches', 'permissions': (('set_yp_compatibility', 'Can set YP compatibility'),)},
        ),
        migrations.AddField(
            model_name='layerbranch',
            name='yp_compatible_version',
            field=models.ForeignKey(to='layerindex.YPCompatibleVersion', blank=True, help_text='Which version of the Yocto Project Compatible program has this layer been approved for for?', verbose_name='Yocto Project Compatible version', on_delete=django.db.models.deletion.SET_NULL, null=True),
        ),
    ]
