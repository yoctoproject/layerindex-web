from layerindex.models import Branch, LayerItem, LayerMaintainer, YPCompatibleVersion, LayerNote, LayerBranch, LayerDependency, Recipe, Machine, Distro, BBClass
from rest_framework import viewsets, serializers
from layerindex.querysethelper import params_to_queryset, get_search_tuple

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

class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = '__all__'

class RecipeViewSet(ParametricSearchableModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

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

