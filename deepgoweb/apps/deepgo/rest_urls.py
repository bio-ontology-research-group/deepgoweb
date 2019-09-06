from __future__ import absolute_import
from django.urls import path, include
from rest_framework.urlpatterns import format_suffix_patterns

from deepgo.rest_views import (
    PredictionsCreateAPIView,
    PredictionsRetrieveAPIView,
    TaxonomyListAPIView)

urlpatterns = [
    path('get/<int:pk>',
        PredictionsRetrieveAPIView.as_view(), name='api-predictions-get'),
    path('create',
        PredictionsCreateAPIView.as_view(), name='api-predictions-create'),
    path('organisms', TaxonomyListAPIView.as_view(), name='api-taxonomy')
]

# urlpatterns = format_suffix_patterns(urlpatterns)
