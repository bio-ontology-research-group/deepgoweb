from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from deepgo.utils import Ontology
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from deepgo.constants import QUALIFIERS
import uuid


class Release(models.Model):
    version = models.CharField(max_length=15, unique=True)
    notes = models.TextField()
    data_root = models.FilePathField(path='data/', allow_files=False, allow_folders=True)
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

    data = models.TextField()
    data_format = models.CharField(
        max_length=10,
        choices=DATA_FORMAT_CHOICES,
        default='fasta')
    user = models.ForeignKey(
        User, related_name='prediction_groups', null=True,
        on_delete=models.SET_NULL)
    date = models.DateTimeField(default=timezone.now)
    threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
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
    def release_version(self):
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
    
    def get_functions(self):
        go = self.group.go
        res = {
            'cellular_component': [],
            'molecular_function': [], 'biological_process': []}
        for i in range(len(self.functions)):
            if self.scores[i] < self.group.threshold:
                continue
            func = self.functions[i]
            if go.has_term(func):
                name = go.get(func)['name']
                res[go.get(func)['namespace']].append(
                    (func, name, self.scores[i]))
        res['cellular_component'] = sorted(
            res['cellular_component'], key=lambda x: x[2], reverse=True)
        res['molecular_function'] = sorted(
            res['molecular_function'], key=lambda x: x[2], reverse=True)
        res['biological_process'] = sorted(
            res['biological_process'], key=lambda x: x[2], reverse=True)
        ret = []
        ret.append({'name': 'Cellular Component', 'functions': res['cellular_component']})
        ret.append({'name': 'Molecular Function', 'functions': res['molecular_function']})
        ret.append({'name': 'Biological Process', 'functions': res['biological_process']})
        return ret
