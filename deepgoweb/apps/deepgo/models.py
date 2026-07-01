from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from deepgo.utils import Ontology
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from deepgo.constants import QUALIFIERS
import uuid
from django.conf import settings

RELEASE_DATA_ROOT = getattr(settings, 'RELEASE_DATA_ROOT', 'data/')

# A model "release" is an archived, versioned, user-selectable snapshot of one
# predictor's assets. DeepGOPlus has always been versioned this way (a per-version
# data_root with go.obo/terms.pkl/train_data.pkl/model.h5); ``predictor_type`` lets
# the SAME table also archive DeepGO-PlusPlus-Light versions (a per-version dgpp
# asset bundle), so both predictors share one changelog, admin, and CafaMetrics path.
PREDICTOR_TYPE_CHOICES = (
    ('deepgoplus', 'DeepGOPlus'),
    ('dgpp-light', 'DeepGO-PlusPlus-Light'),
)


class Release(models.Model):
    version = models.CharField(max_length=15, unique=True)
    # Which predictor this version belongs to. Default 'deepgoplus' keeps every
    # existing row (and the legacy API) on the original behaviour.
    predictor_type = models.CharField(
        max_length=20, choices=PREDICTOR_TYPE_CHOICES, default='deepgoplus')
    notes = models.TextField(blank=True, default='')
    date = models.DateTimeField(default=timezone.now)
    # data_root holds this version's asset directory. For deepgoplus it lives under
    # RELEASE_DATA_ROOT; for dgpp-light under the dgpp assets root. FilePathField's
    # ``path`` only constrains the admin widget, not programmatic (loadrelease) saves,
    # so an out-of-RELEASE_DATA_ROOT dgpp path is stored fine.
    data_root = models.FilePathField(
        path=RELEASE_DATA_ROOT, allow_files=False, allow_folders=True, max_length=512)
    # DeepGOPlus-only per-aspect DIAMOND/CNN blend weights (ignored by dgpp-light).
    alpha_bp = models.FloatField(
        default=0.59, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    alpha_mf = models.FloatField(
        default=0.55, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    alpha_cc = models.FloatField(
        default=0.46, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    def __str__(self):
        return f'{self.get_predictor_type_display()} {self.version}'

    def headline_metric(self):
        """The no-knowledge (else first) CAFA metric row, for compact display."""
        return (self.cafa_metrics.filter(knowledge_class='no_knowledge').first()
                or self.cafa_metrics.first())


class CafaMetrics(models.Model):
    """Reproducibility: the CAFA-style evaluation of one Release, computed offline
    (the cafa6_recon harness + official cafaeval on the ws server) and ingested via
    the ``loadmetrics`` management command. Displayed as the version's "expected
    F-max" on the changelog and result pages. One row per knowledge class."""
    KNOWLEDGE_CHOICES = (
        ('no_knowledge', 'No-knowledge (novel proteins)'),
        ('limited', 'Limited-knowledge'),
        ('partial', 'Partial-knowledge'),
        ('overall', 'Overall'),
    )
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, related_name='cafa_metrics')
    knowledge_class = models.CharField(
        max_length=20, choices=KNOWLEDGE_CHOICES, default='no_knowledge')
    fmax = models.FloatField(help_text='IA-weighted F-max (CAFA official metric)')
    fmax_mf = models.FloatField(null=True, blank=True)
    fmax_bp = models.FloatField(null=True, blank=True)
    fmax_cc = models.FloatField(null=True, blank=True)
    coverage = models.FloatField(null=True, blank=True)
    # Provenance: which protocol/benchmark produced this (e.g. the CAFA6 challenge
    # training cut + leak-free reconstruction), so the number is reproducible.
    protocol = models.CharField(max_length=64, default='cafa6-recon')
    notes = models.TextField(blank=True, default='')
    computed_date = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('release', 'knowledge_class', 'protocol')
        verbose_name_plural = 'CAFA metrics'

    def __str__(self):
        return f'{self.release.version} {self.knowledge_class} f_w={self.fmax:.3f}'


class PredictionGroup(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    DATA_FORMAT_CHOICES = (
        ('enter', 'Raw Sequence'),
        ('fasta', 'FASTA'))

    # Which predictor to run. 'deepgoplus' = the original release-based CNN + DIAMOND
    # model; 'dgpp-light' = DeepGO-PlusPlus-Light, the CPU-only cascade that combines
    # several heterogeneous components (DIAMOND BLAST-KNN, homology-bridged STRING
    # Net-KNN, a hierarchy-aware C-HMCNN CNN over the GO is_a+part_of DAG, an ESM2-35M
    # embedding kNN, and ProteInfer) with a learned per-aspect integrator. The CNN is
    # only one of the components — the model as a whole is a multi-evidence ensemble.
    # See apps/deepgo/dgpp/.
    PREDICTOR_CHOICES = (
        ('deepgoplus', 'DeepGOPlus (CNN + DIAMOND)'),
        ('dgpp-light',
         'DeepGO-PlusPlus-Light — CPU multi-evidence ensemble '
         '(DIAMOND + STRING-Net + hierarchy-aware CNN + ESM2-kNN + ProteInfer)'))

    data = models.TextField()
    data_format = models.CharField(
        max_length=10,
        choices=DATA_FORMAT_CHOICES,
        default='fasta')
    predictor = models.CharField(
        max_length=20, choices=PREDICTOR_CHOICES, default='deepgoplus')
    # DeepGO-PlusPlus-Light only: per-protein, per-component top predictions
    # ([ {component_label: [[go_id, name, score], ...]}, ... ] in protein order),
    # shown on the result page so users see each individual predictor's output.
    component_predictions = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(
        User, related_name='prediction_groups', null=True,
        on_delete=models.SET_NULL)
    date = models.DateTimeField(default=timezone.now)
    threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    # When True (the default), the result view contracts each aspect's predicted
    # GO terms to the most specific ones: any term that is a (true-path) ancestor of
    # another predicted term above the threshold is hidden, since its score is implied
    # by the more specific descendant. The full propagated set is still kept in the
    # stored arrays and the JSON/CSV exports — contraction is display-only.
    contract = models.BooleanField(default=True)
    release = models.ForeignKey(
        Release, related_name='prediction_groups', null=True,
        on_delete=models.SET_NULL)

    @property
    def go(self):
        if hasattr(self, '_go'):
            return self._go
        self._go = Ontology(filename=f'{self.release.data_root}/go.obo')
        return self._go

    @property
    def version(self):
        return self.release.version

class GenomeJob(models.Model):
    """A genome-scale annotation run (DeepGO-GSPA). Unlike per-protein
    :class:`PredictionGroup`, the unit of work is a whole genome / metagenome
    FASTA (+ optional GFF3): CDS are translated, every protein is annotated with
    DeepGO-PlusPlus(-Light), and then **per-contig** genome-scale quality metrics
    and optional SAT taxon-consistency / completeness / coherence enforcement run
    on top. The heavy lifting happens in the separate ``gspa`` service
    (settings.GSPA_SERVICE_URL); this model just carries the inputs, the queued
    status, and the parsed results.

    Inputs are stored as text (not files) so the Celery worker — a different
    container from the web frontend, with no shared media volume — can read them
    straight from the database."""

    STATUS_CHOICES = (
        ('pending', 'Queued'),
        ('running', 'Running'),
        ('done', 'Completed'),
        ('error', 'Failed'))

    PREDICTOR_CHOICES = (
        ('light', 'DeepGO-PlusPlus-Light (CPU, self-contained)'),
        ('full', 'DeepGO-PlusPlus (full)'),
        ('none', 'No prediction (metrics only)'))

    METRICS_SCOPE_CHOICES = (
        ('contig', 'Per contig (recommended)'),
        ('genome', 'Whole genome (pooled)'),
        ('both', 'Both'))

    CONSISTENCY_MODE_CHOICES = (
        ('remove', 'Remove inconsistent terms'),
        ('downrank', 'Down-rank inconsistent terms'),
        ('flag', 'Flag only'),
        ('minimal-flip', 'Minimal-flip (joint MaxSAT)'))

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    user = models.ForeignKey(
        User, related_name='genome_jobs', null=True, blank=True,
        on_delete=models.SET_NULL)

    # --- inputs (text, so the worker can read them without a shared volume) ---
    genome_filename = models.CharField(max_length=255, blank=True, default='')
    genome_data = models.TextField(blank=True, default='')
    gff3_filename = models.CharField(max_length=255, blank=True, default='')
    gff3_data = models.TextField(blank=True, default='')
    proteins_filename = models.CharField(max_length=255, blank=True, default='')
    proteins_data = models.TextField(blank=True, default='')

    # --- options (mirror the gspa annotate / service knobs) ---
    predictor = models.CharField(max_length=10, choices=PREDICTOR_CHOICES, default='light')
    metrics_scope = models.CharField(max_length=10, choices=METRICS_SCOPE_CHOICES, default='contig')
    kingdom = models.CharField(max_length=20, blank=True, default='')
    mag = models.BooleanField(default=False)
    enforce_consistency = models.BooleanField(default=False)
    consistency_mode = models.CharField(
        max_length=15, choices=CONSISTENCY_MODE_CHOICES, default='remove')
    taxon = models.CharField(max_length=40, blank=True, default='')
    enforce_completeness = models.BooleanField(default=False)
    enforce_coherence = models.BooleanField(default=False)
    provenance = models.BooleanField(default=True)
    # Whether to infer the organism taxon from the predictions. Off for proteomes
    # where function-based inference is known-unreliable (archaea / viruses, whose
    # conserved proteins are homologous to other domains), so no wrong organism
    # is asserted. Ignored when `taxon` is set explicitly.
    infer_taxon = models.BooleanField(default=True)

    # --- results (parsed from the gspa service response) ---
    per_contig_metrics = models.JSONField(null=True, blank=True)
    annotations = models.JSONField(null=True, blank=True)
    enforcement_actions = models.JSONField(null=True, blank=True)
    # Organism domain inferred from the predictions via the GO taxon constraints
    # (Asaad-style): inferred_taxon = {'taxon': 'NCBITaxon_2', 'label': 'Bacteria'};
    # taxon_inference = the per-candidate evidence rows.
    inferred_taxon = models.JSONField(null=True, blank=True)
    taxon_inference = models.JSONField(null=True, blank=True)
    # Per-phase wall-clock timing rows: [{'phase','seconds','percent'}, ...].
    timing = models.JSONField(null=True, blank=True)
    log = models.TextField(blank=True, default='')
    error = models.TextField(blank=True, default='')

    def __str__(self):
        return f'GenomeJob {self.uuid} ({self.status})'

    @property
    def is_terminal(self):
        return self.status in ('done', 'error')

    @property
    def n_annotations(self):
        return len(self.annotations or [])

    @property
    def n_contigs(self):
        return len(self.per_contig_metrics or [])


class Prediction(models.Model):
    protein_info = models.CharField(max_length=255, blank=True, null=True)
    sequence = models.TextField()
    functions = ArrayField(
        models.CharField(max_length=15), blank=True, null=True)
    similar_proteins = ArrayField(
        models.CharField(max_length=31), blank=True, null=True)
    similar_scores = ArrayField(models.FloatField(default=0.0), blank=True, null=True)
    scores = ArrayField(models.FloatField(default=0.0), blank=True, null=True)
    group = models.ForeignKey(
        PredictionGroup, related_name='predictions', null=True,
        on_delete=models.SET_NULL)

    def get_similar_proteins(self):
        for i in range(len(self.similar_proteins)):
            yield (self.similar_proteins[i], self.similar_scores[i])

    def function_names(self):
        go = self.group.go
        if self.scores is None:
            for func in self.functions:
                if go.has_term(func):
                    yield (func, go.get(func)['name'])
                else:
                    yield (func, '')
    
    def get_functions(self, contract=None):
        go = self.group.go
        # contract=None -> follow the group's display preference; callers that need
        # the canonical full propagated set (JSON/CSV export) pass contract=False.
        if contract is None:
            contract = getattr(self.group, 'contract', True)
        # Per-aspect map: go_id -> [name, score]. Using a dict lets us merge a term
        # with itself (keep the max score) after obsolete terms are transferred onto
        # their replacements.
        res = {
            'cellular_component': {},
            'molecular_function': {}, 'biological_process': {}}
        for i in range(len(self.functions)):
            if self.scores[i] < self.group.threshold:
                continue
            func = self.functions[i]
            score = self.scores[i]
            # Resolve obsolete terms via the GO replaced_by/consider fields so a
            # predicted-but-obsolete class is transferred to its replacement (or, if
            # there is none, surfaced with an [OBSOLETE] marker) instead of silently
            # vanishing.
            target, status, label = go.resolve_term(func)
            if target is None:
                continue
            if go.is_root_term(target):
                continue
            namespace = go.get_namespace(target)
            if namespace not in res:
                continue
            cur = res[namespace].get(target)
            if cur is None or score > cur[1]:
                res[namespace][target] = [label, score]

        ret = []
        order = [
            ('cellular_component', 'Cellular Component'),
            ('molecular_function', 'Molecular Function'),
            ('biological_process', 'Biological Process')]
        for key, title in order:
            terms = res[key]
            if contract and terms:
                # Hide any term that is a strict ancestor of another shown term:
                # the more specific descendant already implies it (true-path rule).
                shown = set(terms.keys())
                redundant = set()
                for t in shown:
                    anc = go.get_anchestors(t)
                    anc.discard(t)
                    redundant |= (anc & shown)
                terms = {t: v for t, v in terms.items() if t not in redundant}
            functions = sorted(
                ((t, v[0], v[1]) for t, v in terms.items()),
                key=lambda x: x[2], reverse=True)
            ret.append({'name': title, 'functions': functions})
        return ret
