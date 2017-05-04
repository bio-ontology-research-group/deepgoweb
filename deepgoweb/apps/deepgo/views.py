from django.core.urlresolvers import reverse
from django.views.generic import (
    CreateView, DetailView)
from deepgo.forms import PredictionForm

from deepgo.models import PredictionGroup


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
        return context
