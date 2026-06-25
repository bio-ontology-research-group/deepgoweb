from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic import (
    CreateView, DetailView, ListView)
from django.views import View
from deepgo.forms import PredictionForm
from django.shortcuts import render
from django.http import HttpResponse

from deepgo.models import PredictionGroup, Release
from deepgoweb.mixins import ActionMixin
import gzip
from io import BytesIO
from django.utils import timezone
import csv
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def sparql_proxy(request):
    """Forward SPARQL queries from the on-page editor to the Jena Fuseki backend
    (settings.FUSEKI_URL). Lets the SPARQL UI work where the Fuseki service isn't
    fronted by a separate reverse proxy; production may still route /ds via nginx."""
    backend = getattr(settings, 'FUSEKI_URL', 'http://localhost:3330/ds/query')
    accept = request.META.get('HTTP_ACCEPT', 'application/sparql-results+json')
    try:
        if request.method == 'POST':
            resp = requests.post(
                backend, data=request.body, timeout=300,
                headers={'Content-Type': request.META.get('CONTENT_TYPE',
                                                           'application/x-www-form-urlencoded'),
                         'Accept': accept})
        else:
            resp = requests.get(backend, params=request.GET.dict(),
                                headers={'Accept': accept}, timeout=300)
    except requests.RequestException as exc:
        return HttpResponse('SPARQL backend unavailable: %s' % exc, status=502)
    return HttpResponse(
        resp.content, status=resp.status_code,
        content_type=resp.headers.get('Content-Type', 'application/sparql-results+json'))


class SparqlFormView(TemplateView):
    template_name = 'deepgo/sparql.html'

class PredictionCreateView(CreateView):

    template_name = 'deepgo/form.html'
    form_class = PredictionForm

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionCreateView, self).get_context_data(
            *args, **kwargs)
        context['example_uuid'] = '9f0906ae-ed30-4003-8483-844dce56040d'
        return context

    def get_success_url(self):
        return reverse('prediction-detail', kwargs={'uuid': self.object.uuid})


class PredictionDetailView(ActionMixin, DetailView):

    template_name = 'deepgo/view.html'
    model = PredictionGroup
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionDetailView, self).get_context_data(
            *args, **kwargs)
        pg = context['object']
        return context

    def on_download_csv(self, request, action, *args, **kwargs):
        pg = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="predictions.csv"'

        writer = csv.writer(response)
        for pred in pg.predictions.all():
            writer.writerow([pred.protein_info, ])
            # Export the full propagated set regardless of the view's contraction toggle.
            for ont in pred.get_functions(contract=False):
                writer.writerow([ont['name'],])
                for go_id, func, score in ont['functions']:
                    writer.writerow([go_id, func, str(score)])
        return response


class ReleaseListView(ListView):

    template_name = 'deepgo/changelog.html'
    model = Release

    def get_queryset(self, *args, **kwargs):
        queryset = super(ReleaseListView, self).get_queryset(*args, **kwargs)
        return queryset.order_by('-date')
