from __future__ import print_function
from __future__ import absolute_import

from rest_framework import generics
from deepgo.models import PredictionGroup
from deepgo.serializers import (
    PredictionGroupSerializer)


class PredictionsCreateAPIView(generics.CreateAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer

class PredictionsRetrieveAPIView(generics.RetrieveAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer
    
