from django.urls import include, path
from django.contrib.auth.decorators import login_required
from deepgo import views

urlpatterns = [
    path('', views.PredictionCreateView.as_view(), name='prediction'),
    path('detail/<int:pk>', views.PredictionDetailView.as_view(), name='prediction-detail'),
    path('annotations', views.AnnotationsListView.as_view(), name='annotations'),
    path('download', views.AnnotationsDownloadView.as_view(), name='download'),
    path('sparql', views.SparqlFormView.as_view(), name='sparql')
]
