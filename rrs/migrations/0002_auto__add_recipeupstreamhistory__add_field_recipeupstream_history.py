# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'RecipeUpstreamHistory'
        db.create_table('rrs_recipeupstreamhistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('end_date', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('rrs', ['RecipeUpstreamHistory'])

        # Adding field 'RecipeUpstream.history'
        db.add_column('rrs_recipeupstream', 'history',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['rrs.RecipeUpstreamHistory'], null=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting model 'RecipeUpstreamHistory'
        db.delete_table('rrs_recipeupstreamhistory')

        # Deleting field 'RecipeUpstream.history'
        db.delete_column('rrs_recipeupstream', 'history_id')


    models = {
        'layerindex.branch': {
            'Meta': {'object_name': 'Branch'},
            'bitbake_branch': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'short_description': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'sort_priority': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now': 'True', 'blank': 'True'})
        },
        'layerindex.layerbranch': {
            'Meta': {'object_name': 'LayerBranch'},
            'actual_branch': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'branch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Branch']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerItem']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'vcs_last_commit': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'vcs_last_fetch': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'vcs_last_rev': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'vcs_subdir': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'})
        },
        'layerindex.layeritem': {
            'Meta': {'object_name': 'LayerItem'},
            'classic': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index_preference': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'layer_type': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'mailing_list_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'N'", 'max_length': '1'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'usage_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'vcs_web_file_base_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_web_tree_base_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'vcs_web_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
        },
        'layerindex.recipe': {
            'Meta': {'object_name': 'Recipe'},
            'bbclassextend': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'bugtracker': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'depends': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
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
            'src_uri': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'rrs.maintainer': {
            'Meta': {'ordering': "['name']", 'object_name': 'Maintainer'},
            'email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'rrs.milestone': {
            'Meta': {'object_name': 'Milestone'},
            'end_date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'start_date': ('django.db.models.fields.DateField', [], {})
        },
        'rrs.recipedistro': {
            'Meta': {'object_name': 'RecipeDistro'},
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'distro': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"})
        },
        'rrs.recipemaintainer': {
            'Meta': {'object_name': 'RecipeMaintainer'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maintainer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['rrs.Maintainer']"}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"})
        },
        'rrs.recipeupgrade': {
            'Meta': {'object_name': 'RecipeUpgrade'},
            'author_date': ('django.db.models.fields.DateTimeField', [], {}),
            'commit_date': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maintainer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['rrs.Maintainer']", 'null': 'True', 'blank': 'True'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"}),
            'sha1': ('django.db.models.fields.CharField', [], {'max_length': '40', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'rrs.recipeupstream': {
            'Meta': {'object_name': 'RecipeUpstream'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'history': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['rrs.RecipeUpstreamHistory']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'no_update_reason': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        'rrs.recipeupstreamhistory': {
            'Meta': {'object_name': 'RecipeUpstreamHistory'},
            'end_date': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {})
        }
    }

    complete_apps = ['rrs']