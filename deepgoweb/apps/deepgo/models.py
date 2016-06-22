from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User


class Prediction(models.Model):
    sequence = models.TextField()
    functions = ArrayField(models.CharField(max_length=10), blank=True)
    user = models.ForeignKey(User, related_name='predictions')
    date = models.DateTimeField()
