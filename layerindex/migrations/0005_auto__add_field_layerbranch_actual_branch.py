# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'LayerBranch.actual_branch'
        db.add_column('layerindex_layerbranch', 'actual_branch',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=80, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'LayerBranch.actual_branch'
        db.delete_column('layerindex_layerbranch', 'actual_branch')


    models = {
        'layerindex.bbappend': {
            'Meta': {'object_name': 'BBAppend'},
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filepath': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"})
        },
        'layerindex.bbclass': {
            'Meta': {'object_name': 'BBClass'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
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
            'actual_branch': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
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
            'index_preference': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
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
            'bbclassextend': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'bugtracker': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filepath': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'homepage': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'license': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'pn': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'provides': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
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