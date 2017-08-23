from __future__ import absolute_import
from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns

from deepgo.rest_views import (
    PredictionsCreateAPIView,
    PredictionsRetrieveAPIView)

urlpatterns = [
    url(
        r'^get/(?P<pk>\d+)/$',
        PredictionsRetrieveAPIView.as_view(), name='api-predictions-get'),
    url(
        r'^create/$',
        PredictionsCreateAPIView.as_view(), name='api-predictions-create'),
    
]

urlpatterns = format_suffix_patterns(urlpatterns)
