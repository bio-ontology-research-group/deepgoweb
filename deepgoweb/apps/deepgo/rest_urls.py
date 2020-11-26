from __future__ import absolute_import
from django.urls import path, include
from rest_framework.urlpatterns import format_suffix_patterns

from deepgo.rest_views import (
    PredictionsCreateAPIView,
    PredictionsRetrieveAPIView)

urlpatterns = [
    path('get/<uuid:uuid>',
        PredictionsRetrieveAPIView.as_view(), name='api-predictions-get'),
    path('create',
        PredictionsCreateAPIView.as_view(), name='api-predictions-create'),
]

# urlpatterns = format_suffix_patterns(urlpatterns)
