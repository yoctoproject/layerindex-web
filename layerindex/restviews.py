from layerindex.models import Branch, LayerItem, LayerNote, LayerBranch, LayerDependency, Recipe, Machine, Distro, BBClass
from rest_framework import viewsets, serializers
from layerindex.querysethelper import params_to_queryset, get_search_tuple

class ParametricSearchableModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        model = self.__class__.serializer_class.Meta.model
        qs = self.queryset
        (filter_string, search_term, ordering_string) = get_search_tuple(self.request, model)
        return params_to_queryset(model, qs, filter_string, search_term, ordering_string)

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch

class BranchViewSet(ParametricSearchableModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

class LayerItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerItem

class LayerItemViewSet(ParametricSearchableModelViewSet):
    queryset = LayerItem.objects.filter(status__in=['P', 'X'])
    serializer_class = LayerItemSerializer

class LayerBranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerBranch

class LayerBranchViewSet(ParametricSearchableModelViewSet):
    queryset = LayerBranch.objects.filter(layer__status__in=['P', 'X'])
    serializer_class = LayerBranchSerializer

class LayerDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerDependency

class LayerDependencyViewSet(ParametricSearchableModelViewSet):
    queryset = LayerDependency.objects.filter(layerbranch__layer__status__in=['P', 'X'])
    serializer_class = LayerDependencySerializer

class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe

class RecipeViewSet(ParametricSearchableModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine

class MachineViewSet(ParametricSearchableModelViewSet):
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer

class DistroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distro

class DistroViewSet(ParametricSearchableModelViewSet):
    queryset = Distro.objects.all()
    serializer_class = DistroSerializer

class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = BBClass

class ClassViewSet(ParametricSearchableModelViewSet):
    queryset = BBClass.objects.all()
    serializer_class = ClassSerializer
