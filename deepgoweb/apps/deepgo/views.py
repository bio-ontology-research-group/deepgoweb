from django.core.urlresolvers import reverse
from django.views.generic.edit import (
    FormView,)
from deepgo.forms import PredictionForm


class PredictionFormView(FormView):

    template_name = 'deepgo/form.html'
    form_class = PredictionForm

    def get_context_data(self, *args, **kwargs):
        context = super(PredictionFormView, self).get_context_data(
            *args, **kwargs)
        return context

    def form_valid(self, form):
        form.save()
        return super(PredictionFormView, self).form_valid(form)

    def get_success_url(self):
        return reverse('home')
