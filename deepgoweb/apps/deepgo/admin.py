from django.contrib import admin
from deepgo import models


class AnnotationAdmin(admin.ModelAdmin):
    raw_id_fields = ('protein',)

# Register your models here.
admin.site.register(models.Prediction)
admin.site.register(models.PredictionGroup)
admin.site.register(models.Protein)
admin.site.register(models.Taxonomy)
admin.site.register(models.Annotation, AnnotationAdmin)
