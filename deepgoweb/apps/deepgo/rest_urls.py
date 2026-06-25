from __future__ import absolute_import
from django.urls import path, include
from rest_framework.urlpatterns import format_suffix_patterns

from deepgo.rest_views import (
    PredictionsCreateAPIView,
    PredictionsPredictAPIView,
    PredictionsRetrieveAPIView)

urlpatterns = [
    path('get/<uuid:uuid>',
        PredictionsRetrieveAPIView.as_view(), name='api-predictions-get'),
    path('create',
        PredictionsCreateAPIView.as_view(), name='api-predictions-create'),
    # Backwards-compatible predictor-aware endpoint (adds dgpp-light + substreams).
    path('predict',
        PredictionsPredictAPIView.as_view(), name='api-predictions-predict'),
]

# urlpatterns = format_suffix_patterns(urlpatterns)
