# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Branch'
        db.create_table('layerindex_branch', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('bitbake_branch', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('short_description', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('sort_priority', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('layerindex', ['Branch'])

        # Adding model 'LayerItem'
        db.create_table('layerindex_layeritem', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=40)),
            ('status', self.gf('django.db.models.fields.CharField')(default='N', max_length=1)),
            ('layer_type', self.gf('django.db.models.fields.CharField')(max_length=1)),
            ('summary', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('description', self.gf('django.db.models.fields.TextField')()),
            ('vcs_url', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('vcs_web_url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('vcs_web_tree_base_url', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('vcs_web_file_base_url', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('usage_url', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('mailing_list_url', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
        ))
        db.send_create_signal('layerindex', ['LayerItem'])

        # Adding model 'LayerBranch'
        db.create_table('layerindex_layerbranch', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layer', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.LayerItem'])),
            ('branch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.Branch'])),
            ('vcs_subdir', self.gf('django.db.models.fields.CharField')(max_length=40, blank=True)),
            ('vcs_last_fetch', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('vcs_last_rev', self.gf('django.db.models.fields.CharField')(max_length=80, blank=True)),
            ('vcs_last_commit', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('layerindex', ['LayerBranch'])

        # Adding model 'LayerMaintainer'
        db.create_table('layerindex_layermaintainer', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layerbranch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.LayerBranch'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('email', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('responsibility', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('status', self.gf('django.db.models.fields.CharField')(default='A', max_length=1)),
        ))
        db.send_create_signal('layerindex', ['LayerMaintainer'])

        # Adding model 'LayerDependency'
        db.create_table('layerindex_layerdependency', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layerbranch', self.gf('django.db.models.fields.related.ForeignKey')(related_name='dependencies_set', to=orm['layerindex.LayerBranch'])),
            ('dependency', self.gf('django.db.models.fields.related.ForeignKey')(related_name='dependents_set', to=orm['layerindex.LayerItem'])),
        ))
        db.send_create_signal('layerindex', ['LayerDependency'])

        # Adding model 'LayerNote'
        db.create_table('layerindex_layernote', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layer', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.LayerItem'])),
            ('text', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('layerindex', ['LayerNote'])

        # Adding model 'Recipe'
        db.create_table('layerindex_recipe', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layerbranch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.LayerBranch'])),
            ('filename', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('filepath', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('pn', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('pv', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('summary', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('description', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('section', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('license', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('homepage', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
        ))
        db.send_create_signal('layerindex', ['Recipe'])

        # Adding model 'RecipeFileDependency'
        db.create_table('layerindex_recipefiledependency', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('recipe', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.Recipe'])),
            ('layerbranch', self.gf('django.db.models.fields.related.ForeignKey')(related_name='+', to=orm['layerindex.LayerBranch'])),
            ('path', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
        ))
        db.send_create_signal('layerindex', ['RecipeFileDependency'])

        # Adding model 'Machine'
        db.create_table('layerindex_machine', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('layerbranch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['layerindex.LayerBranch'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('layerindex', ['Machine'])


    def backwards(self, orm):
        # Deleting model 'Branch'
        db.delete_table('layerindex_branch')

        # Deleting model 'LayerItem'
        db.delete_table('layerindex_layeritem')

        # Deleting model 'LayerBranch'
        db.delete_table('layerindex_layerbranch')

        # Deleting model 'LayerMaintainer'
        db.delete_table('layerindex_layermaintainer')

        # Deleting model 'LayerDependency'
        db.delete_table('layerindex_layerdependency')

        # Deleting model 'LayerNote'
        db.delete_table('layerindex_layernote')

        # Deleting model 'Recipe'
        db.delete_table('layerindex_recipe')

        # Deleting model 'RecipeFileDependency'
        db.delete_table('layerindex_recipefiledependency')

        # Deleting model 'Machine'
        db.delete_table('layerindex_machine')


    models = {
        'layerindex.branch': {
            'Meta': {'object_name': 'Branch'},
            'bitbake_branch': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'short_description': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'sort_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        'layerindex.layerbranch': {
            'Meta': {'object_name': 'LayerBranch'},
            'branch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Branch']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerItem']"}),
            'vcs_last_commit': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'vcs_last_fetch': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'vcs_last_rev': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'vcs_subdir': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'})
        },
        'layerindex.layerdependency': {
            'Meta': {'object_name': 'LayerDependency'},
            'dependency': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'dependents_set'", 'to': "orm['layerindex.LayerItem']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'dependencies_set'", 'to': "orm['layerindex.LayerBranch']"})
        },
        'layerindex.layeritem': {
            'Meta': {'object_name': 'LayerItem'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layer_type': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'mailing_list_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'N'", 'max_length': '1'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'usage_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'vcs_web_file_base_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_web_tree_base_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_web_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
        },
        'layerindex.layermaintainer': {
            'Meta': {'object_name': 'LayerMaintainer'},
            'email': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'responsibility': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '1'})
        },
        'layerindex.layernote': {
            'Meta': {'object_name': 'LayerNote'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerItem']"}),
            'text': ('django.db.models.fields.TextField', [], {})
        },
        'layerindex.machine': {
            'Meta': {'object_name': 'Machine'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'layerindex.recipe': {
            'Meta': {'object_name': 'Recipe'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filepath': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'homepage': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'license': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'pn': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'pv': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'section': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'})
        },
        'layerindex.recipefiledependency': {
            'Meta': {'object_name': 'RecipeFileDependency'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['layerindex.LayerBranch']"}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"})
        }
    }

    complete_apps = ['layerindex']