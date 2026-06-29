from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic import (
    CreateView, DetailView, ListView)
from django.views import View
from deepgo.forms import GenomeForm, PredictionForm
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
import os

from deepgo.models import GenomeJob, PredictionGroup, Release
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
        # Only expose the example-result link if that PredictionGroup is actually
        # seeded (manage.py seed_example), so a fresh DB never shows a 404 link.
        from deepgo.constants import EXAMPLE_UUID
        if PredictionGroup.objects.filter(uuid=EXAMPLE_UUID).exists():
            context['example_uuid'] = EXAMPLE_UUID
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


class GenomeCreateView(CreateView):
    """DeepGO-GSPA: upload a genome (+GFF3) for genome-scale annotation. Queues
    the async :func:`deepgo.tasks.annotate_genome` and redirects to the result
    page, which polls until the gspa service finishes."""

    template_name = 'deepgo/genome_form.html'
    form_class = GenomeForm

    def form_valid(self, form):
        from deepgo.tasks import annotate_genome
        # super().form_valid saves the job (self.object) and builds the redirect.
        response = super().form_valid(form)
        if self.request.user.is_authenticated:
            self.object.user = self.request.user
            self.object.save(update_fields=['user'])
        annotate_genome.delay(self.object.pk)
        return response

    def get_success_url(self):
        return reverse('genome-detail', kwargs={'uuid': self.object.uuid})


class GenomeExampleView(View):
    """One-click examples for the Genome tab. Loads a small bundled example
    genome (reverse-translated real genes + its GFF3) for the requested domain,
    creates a GenomeJob with sensible defaults (DG++Light, per-contig metrics,
    inferred organism taxon, consistency enforcement, provenance) and runs it —
    the file-upload analogue of the Prediction tab's "Try an example". The
    organism is left to be inferred (no kingdom/taxon asserted), so each example
    also demonstrates the taxon inference recovering the right lineage."""

    EXAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'examples')

    # slug -> (file prefix, infer_taxon). Function-based taxon inference is only
    # reliable for bacteria/eukaryotes; for archaea (informational machinery
    # homologous to eukaryotes) and viruses (host-homologous or DB-absent
    # proteins) it is left OFF so the demo never asserts a wrong organism.
    EXAMPLES = {
        'eukaryote': ('eukaryote', True),   # infers Fungi (bias aligns with truth)
        'bacteria':  ('bacteria',  False),  # mis-infers at scale (see note)
        'archaea':   ('archaea',   False),
        'phage':     ('phage',     False),
    }

    def get(self, request, *args, **kwargs):
        from deepgo.tasks import annotate_genome
        slug = request.GET.get('organism', 'bacteria')
        prefix, infer = self.EXAMPLES.get(slug, self.EXAMPLES['bacteria'])
        fna = f'{prefix}_genome.fna'
        gff = f'{prefix}_genome.gff3'
        with open(os.path.join(self.EXAMPLE_DIR, fna)) as fh:
            genome_data = fh.read()
        with open(os.path.join(self.EXAMPLE_DIR, gff)) as fh:
            gff3_data = fh.read()
        job = GenomeJob.objects.create(
            genome_filename=fna, genome_data=genome_data,
            gff3_filename=gff, gff3_data=gff3_data,
            predictor='light', metrics_scope='contig',
            enforce_consistency=True, consistency_mode='remove',
            provenance=True, infer_taxon=infer, status='pending',
            user=request.user if request.user.is_authenticated else None)
        annotate_genome.delay(job.pk)
        return HttpResponseRedirect(
            reverse('genome-detail', kwargs={'uuid': job.uuid}))


class GenomeDetailView(ActionMixin, DetailView):
    """Result page for a genome job. While pending/running the template
    auto-refreshes; when done it shows the per-contig metrics table, the
    annotations (with provenance) and the enforcement-actions log."""

    template_name = 'deepgo/genome_view.html'
    model = GenomeJob
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'

    # Valid GO/GAF evidence codes; anything else is normalised to IEA (electronic).
    GAF_EVIDENCE = {
        'EXP', 'IDA', 'IPI', 'IMP', 'IGI', 'IEP', 'HTP', 'HDA', 'HMP', 'HGI', 'HEP',
        'IBA', 'IBD', 'IKR', 'IRD', 'ISS', 'ISO', 'ISA', 'ISM', 'IGC', 'RCA',
        'TAS', 'NAS', 'IC', 'ND', 'IEA',
    }
    ASPECT_CODE = {'MF': 'F', 'BP': 'P', 'CC': 'C'}
    ASPECT_RELATION = {'F': 'enables', 'P': 'involved_in', 'C': 'located_in'}

    def get_context_data(self, **kwargs):
        """Build a per-protein summary and per-aspect totals from the annotations
        so the result page shows every protein distinctly (not 500 rows of one)."""
        ctx = super().get_context_data(**kwargs)
        rows = self.object.annotations or []
        per = {}
        aspect_totals = {'MF': 0, 'BP': 0, 'CC': 0}
        distinct = set()
        for r in rows:
            if (r.get('type') or 'GO') != 'GO':
                continue
            pid = r.get('protein_id') or ''
            try:
                sc = float(r.get('score') or 0)
            except (TypeError, ValueError):
                sc = 0.0
            asp = r.get('aspect') or ''
            distinct.add(r.get('value'))
            d = per.get(pid)
            if d is None:
                d = per[pid] = {'protein': pid, 'n': 0, 'nc': 0,
                                'MF': 0, 'BP': 0, 'CC': 0}
            d['n'] += 1
            if sc >= 0.5:                       # confident calls drive the summary
                d['nc'] += 1
                if asp in ('MF', 'BP', 'CC'):
                    d[asp] += 1
                    aspect_totals[asp] += 1
        ctx['protein_summary'] = sorted(per.values(),
                                        key=lambda x: (-x['nc'], x['protein']))
        ctx['aspect_totals'] = aspect_totals
        ctx['distinct_terms'] = len(distinct)
        ctx['has_aspect'] = sum(aspect_totals.values()) > 0
        return ctx

    def on_download_csv(self, request, action, *args, **kwargs):
        job = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="gspa_annotations.csv"'
        writer = csv.writer(response)
        rows = job.annotations or []
        if rows:
            header = list(rows[0].keys())
            writer.writerow(header)
            for row in rows:
                writer.writerow([row.get(h, '') for h in header])
        return response

    def on_download_gaf(self, request, action, *args, **kwargs):
        """Standard GO annotation file (GAF 2.2) of the predicted/enforced
        annotations — the interoperable format (loads in any GO tool), built from
        the annotation rows, their aspect, and the inferred organism taxon."""
        import datetime
        import re
        job = self.get_object()
        rows = job.annotations or []

        taxon = 'taxon:0'
        it = job.inferred_taxon if isinstance(job.inferred_taxon, dict) else {}
        m = re.search(r'(\d+)', (it or {}).get('taxon') or '')
        if m:
            taxon = 'taxon:' + m.group(1)
        today = datetime.date.today().strftime('%Y%m%d')

        lines = ['!gaf-version: 2.2',
                 '!generated-by: DeepGO-GSPA',
                 '!date-generated: ' + today]
        for r in rows:
            if (r.get('type') or 'GO') != 'GO':
                continue
            aspect = self.ASPECT_CODE.get(r.get('aspect') or '')
            if not aspect:                       # GAF requires the aspect column
                continue
            ev = (r.get('evidence') or 'IEA').strip().upper()
            if ev not in self.GAF_EVIDENCE:
                ev = 'IEA'
            pid = r.get('protein_id') or ''
            cols = [
                'DeepGO-GSPA',                   # 1  DB
                pid,                             # 2  DB Object ID
                pid,                             # 3  DB Object Symbol
                self.ASPECT_RELATION[aspect],    # 4  Qualifier / relation
                r.get('value') or '',            # 5  GO ID
                'DeepGO-GSPA:prediction',        # 6  DB:Reference
                ev,                              # 7  Evidence code
                '',                              # 8  With/From
                aspect,                          # 9  Aspect (F/P/C)
                '',                              # 10 DB Object Name
                '',                              # 11 DB Object Synonym
                'protein',                       # 12 DB Object Type
                taxon,                           # 13 Taxon
                today,                           # 14 Date
                'DeepGO-GSPA',                   # 15 Assigned By
                '',                              # 16 Annotation Extension
                '',                              # 17 Gene Product Form ID
            ]
            lines.append('\t'.join(cols))

        response = HttpResponse('\n'.join(lines) + '\n',
                                content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="gspa_annotations.gaf"'
        return response


class ReleaseListView(ListView):

    template_name = 'deepgo/changelog.html'
    model = Release

    def get_queryset(self, *args, **kwargs):
        queryset = super(ReleaseListView, self).get_queryset(*args, **kwargs)
        return queryset.order_by('-date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Release.objects.prefetch_related('cafa_metrics').order_by('-date')
        # (section label, releases) pairs; the template renders one block each.
        ctx['sections'] = [
            ('DeepGOPlus', qs.filter(predictor_type='deepgoplus')),
            ('DeepGO-PlusPlus-Light', qs.filter(predictor_type='dgpp-light')),
        ]
        return ctx
