from django.urls import include, path
from django.contrib.auth.decorators import login_required
from deepgo.views import (
    PredictionDetailView,
    PredictionCreateView)

urlpatterns = [
    path('', PredictionCreateView.as_view(), name='prediction'),
    path('detail/<int:pk>', PredictionDetailView.as_view(), name='prediction-detail'),
]
