from __future__ import print_function
from __future__ import absolute_import

from rest_framework import generics
from rest_framework.response import Response
from deepgo.models import PredictionGroup, Taxonomy
from deepgo.serializers import (
    PredictionGroupSerializer, TaxonomySerializer)


class PredictionsCreateAPIView(generics.CreateAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer

class PredictionsRetrieveAPIView(generics.RetrieveAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer
    lookup_field='uuid'
    pk_url_kwarg = 'uuid'
    

class TaxonomyListAPIView(generics.ListAPIView):
    queryset = Taxonomy.objects.all()
    serializer_class = TaxonomySerializer

    def list(self, request):
        query = request.GET.get('query', None)
        if query is None or len(query) < 3:
            return Response([])
        queryset = self.get_queryset()
        queryset = queryset.filter(name__istartswith=query)
        serializer = TaxonomySerializer(queryset, many=True)
        return Response(serializer.data)
