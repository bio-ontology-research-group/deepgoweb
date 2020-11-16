from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic import (
    CreateView, DetailView, ListView)
from django.views import View
from deepgo.forms import PredictionForm, DownloadForm
from django.shortcuts import render
from django.http import HttpResponse

from deepgo.models import PredictionGroup, Annotation
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


class AnnotationsListView(ActionMixin, ListView):
    template_name = 'deepgo/annotations.html'
    model = Annotation
    paginate_by = 10

    def get_queryset(self, *args, **kwargs):
        queryset = super(
            AnnotationsListView, self).get_queryset(*args, **kwargs)
        return queryset


class AnnotationsDownloadView(View):
    template_name = 'deepgo/download.html'
    
    def get(self, request, *args, **kwargs):
        context = {'form': DownloadForm()}
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        form = DownloadForm(request.POST)
        if not form.is_valid():
            context = {'form': form}
            return render(request, self.template_name, context)
        
        data = form.cleaned_data
        org_id = data['org_id']
        annots = Annotation.objects.filter(protein__taxon_id=org_id)[:100]
        
        zbuf = BytesIO()
        zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=zbuf)
        zfile.write('!gpa-version: 1.1\n\n'.encode('utf-8'))
        zfile.write('!DeepGOPlus predictions\n\n'.encode('utf-8'))
        for annot in annots:
            prot = annot.protein
            qual = annot.qualifier
            date = timezone.now()
            date = f'{date.year}{date.month:02d}{date.day:02d}'
            zfile.write(
                f'UniProtKB\t{prot.acc_id}\t{qual}\t{annot.function}\t\tECO:0000203\t\t\t{date}\tDeepGOPlus\t\tscore={annot.score}\n'.encode('utf-8'))
        zfile.close()
        
        compressed_content = zbuf.getvalue()
        response = HttpResponse(compressed_content)
        response['Content-Type'] = 'application/gzip'
        response['Content-Disposition'] = f'attachment; filename="goa-{org_id}.gpad.gz"'
        response['Content-Length'] = str(len(compressed_content))
        return response
