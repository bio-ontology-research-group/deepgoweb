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

class Release(models.Model):
    version = models.CharField(max_length=15, unique=True)
    notes = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    data_root = models.FilePathField(
        path=RELEASE_DATA_ROOT, allow_files=False, allow_folders=True)
    alpha_bp = models.FloatField(
        default=0.59, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    alpha_mf = models.FloatField(
        default=0.55, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    alpha_cc = models.FloatField(
        default=0.46, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    def __str__(self):
        return f'Version - {self.version}'


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
