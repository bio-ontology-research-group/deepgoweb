from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User
from deepgo.utils import go


class PredictionGroup(models.Model):
    DATA_FORMAT_CHOICES = (
        ('enter', 'Raw Sequence'),)

    data = models.TextField()
    data_format = models.CharField(
        max_length=10,
        choices=DATA_FORMAT_CHOICES,
        default='enter')
    user = models.ForeignKey(User, related_name='prediction_groups', null=True)
    date = models.DateTimeField()


class Prediction(models.Model):
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
