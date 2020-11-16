from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from deepgo.utils import go
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from deepgo.constants import QUALIFIERS
import uuid


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

    def function_names(self):
        if self.scores is None:
            for func in self.functions:
                if go.has_term(func):
                    yield (func, go.get(func)['name'])
                else:
                    yield (func, '')
    
    def get_functions(self):
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


class Taxonomy(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return str(self.id)
                
class Protein(models.Model):
    id = models.BigIntegerField(primary_key=True)
    acc_id = models.CharField(max_length=15, unique=True)
    pro_id = models.CharField(max_length=31, db_index=True)
    name = models.CharField(max_length=255)
    gene = models.CharField(max_length=63, blank=True, null=True)
    taxon = models.ForeignKey(
        Taxonomy, on_delete=models.SET_NULL, db_index=True,
        blank=True, null=True, related_name='proteins')
    reviewed = models.BooleanField(default=False)

    class Meta:

        index_together = [
            ['id', 'taxon'],
        ]

    def __str__(self):
        return self.acc_id
    
    
class Annotation(models.Model):
    protein = models.ForeignKey(
        Protein, on_delete=models.CASCADE, db_index=True,
        related_name='annotations')
    go_id = models.PositiveIntegerField(db_index=True)
    score = models.PositiveIntegerField()

    class Meta:

        unique_together = [
            ['protein', 'go_id'],
        ]

    @property
    def function(self):
        return f'GO:{self.go_id:07d}'

    @property
    def label(self):
        return go.get(self.function)['label']

    @property
    def namespace(self):
        return go.get(self.function)['namespace']

    @property
    def qualifier(self):
        return QUALIFIERS[self.namespace]
