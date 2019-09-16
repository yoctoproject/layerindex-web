# OpenEmbedded Layer Index REST API implementation
#
# Copyright (C) 2014, 2016-2019 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details

from layerindex.models import Branch, LayerItem, LayerMaintainer, YPCompatibleVersion, LayerNote, LayerBranch, LayerDependency, Recipe, Machine, Distro, BBClass, Source, Patch, PackageConfig, StaticBuildDep, DynamicBuildDep, RecipeFileDependency, BBAppend, IncFile
from rest_framework import viewsets, serializers, pagination
from layerindex.querysethelper import params_to_queryset, get_search_tuple

class LayerIndexPagination(pagination.PageNumberPagination):
    page_size = 200

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional "fields" argument that
    controls which fields should be displayed. Borrowed from the Django
    REST Framework documentation.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

class ParametricSearchableModelViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        model = self.__class__.serializer_class.Meta.model
        qs = self.queryset
        (filter_string, search_term, ordering_string) = get_search_tuple(self.request, model)
        return params_to_queryset(model, qs, filter_string, search_term, ordering_string)

class BranchSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'

class BranchViewSet(ParametricSearchableModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

class LayerItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerItem
        fields = '__all__'

class LayerItemViewSet(ParametricSearchableModelViewSet):
    queryset = LayerItem.objects.filter(status__in=['P', 'X'])
    serializer_class = LayerItemSerializer

class LayerBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerBranch
        fields = '__all__'

class LayerBranchViewSet(ParametricSearchableModelViewSet):
    queryset = LayerBranch.objects.filter(layer__status__in=['P', 'X'])
    serializer_class = LayerBranchSerializer

class LayerDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerDependency
        fields = '__all__'

class LayerDependencyViewSet(ParametricSearchableModelViewSet):
    queryset = LayerDependency.objects.filter(layerbranch__layer__status__in=['P', 'X'])
    serializer_class = LayerDependencySerializer

class LayerMaintainerSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = LayerMaintainer
        fields = '__all__'

class LayerMaintainerViewSet(ParametricSearchableModelViewSet):
    queryset = LayerMaintainer.objects.filter(layerbranch__layer__status__in=['P', 'X'])
    serializer_class = LayerMaintainerSerializer

class LayerNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerNote
        fields = '__all__'

class LayerNoteViewSet(ParametricSearchableModelViewSet):
    queryset = LayerNote.objects.filter(layer__status__in=['P', 'X'])
    serializer_class = LayerNoteSerializer

class SourceSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Source
        fields = '__all__'

class PatchSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Patch
        fields = '__all__'

class PackageConfigSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = PackageConfig
        fields = '__all__'

    builddeps = serializers.SerializerMethodField()

    def get_builddeps(self, package_config):
        return package_config.dynamicbuilddep_set.values_list('name', flat=True)

class RecipeFileDependencySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = RecipeFileDependency
        fields = '__all__'

class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = '__all__'

class RecipeViewSet(ParametricSearchableModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class RecipeExtendedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = '__all__'

    sources = serializers.SerializerMethodField()
    patches = serializers.SerializerMethodField()
    package_configs = serializers.SerializerMethodField()
    staticbuilddeps = serializers.SerializerMethodField()
    filedeps = serializers.SerializerMethodField()

    def get_sources(self, recipe):
        qs = recipe.source_set.all()
        serializer = SourceSerializer(instance=qs, many=True, read_only=True, fields=('url', 'sha256sum'))
        return serializer.data

    def get_patches(self, recipe):
        qs = recipe.patch_set.all()
        serializer = PatchSerializer(instance=qs, many=True, read_only=True, fields=('path', 'src_path', 'status', 'status_extra', 'apply_order', 'applied', 'striplevel'))
        return serializer.data

    def get_package_configs(self, recipe):
        qs = recipe.packageconfig_set.all()
        serializer = PackageConfigSerializer(instance=qs, many=True, read_only=True, fields=('feature', 'with_option', 'without_option', 'builddeps'))
        return serializer.data

    def get_staticbuilddeps(self, recipe):
        return recipe.staticbuilddep_set.values_list('name', flat=True)

    def get_filedeps(self, recipe):
        qs = recipe.recipefiledependency_set.all()
        serializer = RecipeFileDependencySerializer(instance=qs, many=True, read_only=True, fields=('layerbranch', 'path'))
        return serializer.data

class RecipeExtendedViewSet(ParametricSearchableModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeExtendedSerializer
    pagination_class = LayerIndexPagination

class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = '__all__'

class MachineViewSet(ParametricSearchableModelViewSet):
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer

class DistroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distro
        fields = '__all__'

class DistroViewSet(ParametricSearchableModelViewSet):
    queryset = Distro.objects.all()
    serializer_class = DistroSerializer

class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = BBClass
        fields = '__all__'

class ClassViewSet(ParametricSearchableModelViewSet):
    queryset = BBClass.objects.all()
    serializer_class = ClassSerializer

class YPCompatibleVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = YPCompatibleVersion
        fields = '__all__'

class LayerSerializer(serializers.ModelSerializer):
    """
    A more fleshed-out LayerBranch serializer for external applications
    """
    branch = BranchSerializer(read_only=True, fields=('id', 'name'))
    layer = LayerItemSerializer(read_only=True)
    yp_compatible_version = YPCompatibleVersionSerializer(read_only=True)
    maintainers = serializers.SerializerMethodField()

    class Meta:
        model = LayerBranch
        fields = '__all__'

    def get_maintainers(self, layerbranch):
        qs = layerbranch.layermaintainer_set.filter(status='A')
        serializer = LayerMaintainerSerializer(instance=qs, many=True, read_only=True, fields=('name', 'email', 'responsibility'))
        return serializer.data

class LayerViewSet(ParametricSearchableModelViewSet):
    """
    A more fleshed-out LayerBranch viewset for external applications
    """
    queryset = LayerBranch.objects.filter(layer__status__in=['P', 'X'])
    serializer_class = LayerSerializer

class AppendSerializer(serializers.ModelSerializer):
    class Meta:
        model = BBAppend
        fields = '__all__'

class AppendViewSet(ParametricSearchableModelViewSet):
    queryset = BBAppend.objects.all()
    serializer_class = AppendSerializer

class IncFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncFile
        fields = '__all__'

class IncFileViewSet(ParametricSearchableModelViewSet):
    queryset = IncFile.objects.all()
    serializer_class = IncFileSerializer

