from django.contrib import admin
from deepgo import models


# Register your models here.
admin.site.register(models.Prediction)
admin.site.register(models.PredictionGroup)
admin.site.register(models.Release)
