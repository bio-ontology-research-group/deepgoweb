from django import forms
from deepgo.models import Prediction, PredictionGroup
import datetime
from deepgo.tasks import predict_functions
from django.core.exceptions import ValidationError
from deepgo.utils import go, get_anchestors


def filter_specific(gos):
    go_set = set()
    for go_id in gos:
        go_set.add(go_id)
    for go_id in gos:
        anchestors = get_anchestors(go, go_id)
        anchestors.discard(go_id)
        go_set -= anchestors
    return list(go_set)


class PredictionForm(forms.ModelForm):

    class Meta:
        model = PredictionGroup
        fields = ['data', 'data_format']

    def clean_data_format(self):
        data_format = self.cleaned_data['data_format']
        if data_format != 'enter':
            raise ValidationError(
                'Only splitted by enters format is supported')
        return data_format

    def save(self):
        self.instance.date = datetime.datetime.now()
        data = self.cleaned_data['data']
        data = data.replace(' ', '')
        sequences = data.split()
        n = len(sequences)
        preds = predict_functions.delay(sequences)
        preds = preds.get()
        cc = preds[0: n]
        mf = preds[n: n + n]
        bp = preds[2 * n: 3 * n]
        self.instance.save()
        predictions = list()
        for i in range(n):
            pred = Prediction(sequence=sequences[i])
            pred.functions = filter_specific(cc[i] + mf[i] + bp[i])
            pred.group = self.instance
            predictions.append(pred)
        Prediction.objects.bulk_create(predictions)
        return self.instance
