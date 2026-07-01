from django.urls import include, path
from django.contrib.auth.decorators import login_required
from deepgo import views

urlpatterns = [
    path('', views.PredictionCreateView.as_view(), name='prediction'),
    path('detail/<uuid:uuid>', views.PredictionDetailView.as_view(), name='prediction-detail'),
    path('genome', views.GenomeCreateView.as_view(), name='genome'),
    path('genome/example', views.GenomeExampleView.as_view(), name='genome-example'),
    path('genome/detail/<uuid:uuid>', views.GenomeDetailView.as_view(), name='genome-detail'),
    path('sparql', views.SparqlFormView.as_view(), name='sparql'),
    path('changelog', views.ReleaseListView.as_view(), name='changelog')
]
