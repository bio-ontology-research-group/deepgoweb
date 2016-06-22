from django.conf.urls import include, url
from django.contrib.auth.decorators import login_required
from deepgo.views import PredictionFormView

urlpatterns = [
    url(r'^$', PredictionFormView.as_view(), name='deepgo-prediction'),
]
