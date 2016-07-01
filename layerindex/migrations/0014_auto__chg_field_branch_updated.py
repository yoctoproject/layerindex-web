# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'Branch.updated'
        db.alter_column('layerindex_branch', 'updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, null=True))

    def backwards(self, orm):

        # Changing field 'Branch.updated'
        db.alter_column('layerindex_branch', 'updated', self.gf('django.db.models.fields.DateTimeField')(auto_now=True))

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'symmetrical': 'False', 'to': "orm['auth.Permission']"})
        },
        'auth.permission': {
            'Meta': {'unique_together': "(('content_type', 'codename'),)", 'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75'}),
            'first_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'symmetrical': 'False', 'to': "orm['auth.Group']", 'related_name': "'user_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'symmetrical': 'False', 'to': "orm['auth.Permission']", 'related_name': "'user_set'"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'db_table': "'django_content_type'", 'unique_together': "(('app_label', 'model'),)", 'ordering': "('name',)", 'object_name': 'ContentType'},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'layerindex.bbappend': {
            'Meta': {'object_name': 'BBAppend'},
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filepath': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
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
            'short_description': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '50'}),
            'sort_priority': ('django.db.models.fields.IntegerField', [], {'blank': 'True', 'null': 'True'}),
            'update_environment': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'on_delete': 'models.SET_NULL', 'null': 'True', 'to': "orm['layerindex.PythonEnvironment']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True', 'null': 'True'}),
            'updates_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'layerindex.classicrecipe': {
            'Meta': {'object_name': 'ClassicRecipe', '_ormbases': ['layerindex.Recipe']},
            'classic_category': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'cover_comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'cover_layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'on_delete': 'models.SET_NULL', 'null': 'True', 'to': "orm['layerindex.LayerBranch']"}),
            'cover_pn': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'cover_status': ('django.db.models.fields.CharField', [], {'default': "'U'", 'max_length': '1'}),
            'cover_verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'recipe_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['layerindex.Recipe']", 'unique': 'True', 'primary_key': 'True'})
        },
        'layerindex.layerbranch': {
            'Meta': {'object_name': 'LayerBranch'},
            'actual_branch': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '80'}),
            'branch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Branch']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerItem']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True'}),
            'vcs_last_commit': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'vcs_last_fetch': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'}),
            'vcs_last_rev': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '80'}),
            'vcs_subdir': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '40'})
        },
        'layerindex.layerdependency': {
            'Meta': {'object_name': 'LayerDependency'},
            'dependency': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerItem']", 'related_name': "'dependents_set'"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']", 'related_name': "'dependencies_set'"})
        },
        'layerindex.layeritem': {
            'Meta': {'object_name': 'LayerItem'},
            'classic': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index_preference': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'layer_type': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'mailing_list_url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '40', 'unique': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'N'", 'max_length': '1'}),
            'summary': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True'}),
            'usage_url': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'vcs_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'vcs_web_file_base_url': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'vcs_web_tree_base_url': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'vcs_web_url': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'})
        },
        'layerindex.layermaintainer': {
            'Meta': {'object_name': 'LayerMaintainer'},
            'email': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'responsibility': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '200'}),
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
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True'})
        },
        'layerindex.pythonenvironment': {
            'Meta': {'object_name': 'PythonEnvironment'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'python_command': ('django.db.models.fields.CharField', [], {'default': "'python'", 'max_length': '255'}),
            'virtualenv_path': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'})
        },
        'layerindex.recipe': {
            'Meta': {'object_name': 'Recipe'},
            'bbclassextend': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'blacklisted': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'bugtracker': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'filepath': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'homepage': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'inherits': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']"}),
            'license': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '2048'}),
            'pn': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'provides': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '2048'}),
            'pv': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'section': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'summary': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '200'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True'})
        },
        'layerindex.recipechange': {
            'Meta': {'object_name': 'RecipeChange'},
            'bugtracker': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'changeset': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.RecipeChangeset']"}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'homepage': ('django.db.models.fields.URLField', [], {'blank': 'True', 'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']", 'related_name': "'+'"}),
            'section': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'}),
            'summary': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '100'})
        },
        'layerindex.recipechangeset': {
            'Meta': {'object_name': 'RecipeChangeset'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'layerindex.recipefiledependency': {
            'Meta': {'object_name': 'RecipeFileDependency'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'layerbranch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.LayerBranch']", 'related_name': "'+'"}),
            'path': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '255'}),
            'recipe': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['layerindex.Recipe']"})
        }
    }

    complete_apps = ['layerindex']