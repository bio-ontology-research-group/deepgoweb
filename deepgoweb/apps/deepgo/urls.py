from django.urls import include, path
from django.contrib.auth.decorators import login_required
from deepgo import views

urlpatterns = [
    path('', views.PredictionCreateView.as_view(), name='prediction'),
    path('detail/<uuid:uuid>', views.PredictionDetailView.as_view(), name='prediction-detail'),
    path('sparql', views.SparqlFormView.as_view(), name='sparql'),
    path('changelog', views.ReleaseListView.as_view(), name='changelog')
]
