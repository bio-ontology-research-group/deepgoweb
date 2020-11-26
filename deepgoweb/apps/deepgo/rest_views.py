from __future__ import print_function
from __future__ import absolute_import

from rest_framework import generics
from rest_framework.response import Response
from deepgo.models import PredictionGroup
from deepgo.serializers import (
    PredictionGroupSerializer)


class PredictionsCreateAPIView(generics.CreateAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer

class PredictionsRetrieveAPIView(generics.RetrieveAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer
    lookup_field='uuid'
    pk_url_kwarg = 'uuid'
