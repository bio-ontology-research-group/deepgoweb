from __future__ import print_function
from __future__ import absolute_import

from rest_framework import generics
from rest_framework.response import Response
from deepgo.models import PredictionGroup
from deepgo.serializers import (
    PredictionGroupSerializer,
    PredictionGroupV2Serializer)


class PredictionsCreateAPIView(generics.CreateAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer


class PredictionsPredictAPIView(generics.CreateAPIView):
    """Predictor-aware endpoint (``api/predict``). Backwards-compatible addition:
    accepts a ``predictor`` field (default ``deepgoplus``) and, for
    ``dgpp-light``, also returns per-component substreams under ``components``.
    The legacy ``api/create`` endpoint above is untouched."""
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupV2Serializer

class PredictionsRetrieveAPIView(generics.RetrieveAPIView):
    queryset = PredictionGroup.objects.all()
    serializer_class = PredictionGroupSerializer
    lookup_field='uuid'
    pk_url_kwarg = 'uuid'
