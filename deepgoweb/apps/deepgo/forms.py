from django import forms
from deepgo.models import Prediction


class PredictionForm(forms.ModelForm):

    class Meta:
        model = Prediction
        fields = ['sequence', ]
