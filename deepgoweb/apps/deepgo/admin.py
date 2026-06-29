from django.contrib import admin
from deepgo import models


class CafaMetricsInline(admin.TabularInline):
    model = models.CafaMetrics
    extra = 0


@admin.register(models.Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ('version', 'predictor_type', 'date')
    list_filter = ('predictor_type',)
    search_fields = ('version',)
    inlines = [CafaMetricsInline]


@admin.register(models.CafaMetrics)
class CafaMetricsAdmin(admin.ModelAdmin):
    list_display = ('release', 'knowledge_class', 'fmax', 'fmax_mf',
                    'fmax_bp', 'fmax_cc', 'protocol')
    list_filter = ('knowledge_class', 'protocol')


admin.site.register(models.Prediction)
admin.site.register(models.PredictionGroup)
admin.site.register(models.GenomeJob)
