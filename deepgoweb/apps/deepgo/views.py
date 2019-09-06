from django.urls import reverse
from django.views.generic import (
    CreateView, DetailView, ListView)
from deepgo.forms import PredictionForm

from deepgo.models import PredictionGroup, Annotation
from deepgoweb.mixins import ActionMixin


class PredictionCreateView(CreateView):

    template_name = 'deepgo/form.html'
    form_class = PredictionForm

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionCreateView, self).get_context_data(
            *args, **kwargs)
        return context

    def get_success_url(self):
        return reverse('prediction-detail', kwargs={'pk': self.object.pk})


class PredictionDetailView(DetailView):

    template_name = 'deepgo/view.html'
    model = PredictionGroup

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionDetailView, self).get_context_data(
            *args, **kwargs)
        pg = context['object']
        return context


class AnnotationsListView(ActionMixin, ListView):
    template_name = 'deepgo/annotations.html'
    model = Annotation
    paginate_by = 10

    def get_queryset(self, *args, **kwargs):
        queryset = super(
            AnnotationsListView, self).get_queryset(*args, **kwargs)
        return queryset

    
