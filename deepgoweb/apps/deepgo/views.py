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


class SparqlFormView(TemplateView):
    template_name = 'deepgo/sparql.html'

class PredictionCreateView(CreateView):

    template_name = 'deepgo/form.html'
    form_class = PredictionForm

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionCreateView, self).get_context_data(
            *args, **kwargs)
        return context

    def get_success_url(self):
        return reverse('prediction-detail', kwargs={'uuid': self.object.uuid})


class PredictionDetailView(DetailView):

    template_name = 'deepgo/view.html'
    model = PredictionGroup
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionDetailView, self).get_context_data(
            *args, **kwargs)
        pg = context['object']
        return context


class ReleaseListView(ListView):

    template_name = 'deepgo/changelog.html'
    model = Release

    def get_queryset(self, *args, **kwargs):
        queryset = super(ReleaseListView, self).get_queryset(*args, **kwargs)
        return queryset.order_by('-date')
