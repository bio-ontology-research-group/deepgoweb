from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from deepgo.utils import go
from django.core.validators import MaxValueValidator, MinValueValidator


class PredictionGroup(models.Model):
    DATA_FORMAT_CHOICES = (
        ('enter', 'Raw Sequence'),
        ('fasta', 'FASTA'))

    data = models.TextField()
    data_format = models.CharField(
        max_length=10,
        choices=DATA_FORMAT_CHOICES,
        default='fasta')
    user = models.ForeignKey(User, related_name='prediction_groups', null=True)
    date = models.DateTimeField()
    threshold = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])


class Prediction(models.Model):
    protein_info = models.CharField(max_length=255, blank=True, null=True)
    sequence = models.TextField()
    functions = ArrayField(
        models.CharField(max_length=10), blank=True, null=True)
    group = models.ForeignKey(
        PredictionGroup, related_name='predictions', null=True)

    def function_names(self):
        for func in self.functions:
            if func in go:
                yield (func, go[func]['name'])
            else:
                yield (func, '')

                
class Protein(models.Model):
    uni_accession = models.CharField(max_length=16, unique=True)
    uni_entry_id = models.CharField(max_length=16, unique=True)
    sequence = models.TextField()
    sequence_md5 = models.CharField(max_length=32, db_index=True)
    ppi_embedding = ArrayField(models.FloatField())
