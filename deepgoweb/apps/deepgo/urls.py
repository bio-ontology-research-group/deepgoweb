from django.conf.urls import include, url
from django.contrib.auth.decorators import login_required
from deepgo.views import (
    PredictionDetailView,
    PredictionCreateView)

urlpatterns = [
    url(r'^$', PredictionCreateView.as_view(), name='prediction'),
    url(r'^detail/(?P<pk>\d+)/$', PredictionDetailView.as_view(), name='prediction-detail'),
]
