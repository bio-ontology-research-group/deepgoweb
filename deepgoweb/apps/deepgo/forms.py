from django import forms
from deepgo.models import Prediction, PredictionGroup
import datetime
from deepgo.tasks import predict_functions
from django.core.exceptions import ValidationError
from deepgo.utils import (
    is_ok, read_fasta, filter_specific)
from deepgo.constants import MAXLEN


class PredictionForm(forms.ModelForm):

    threshold = forms.FloatField(
        initial=0.3,
        min_value=0.0, max_value=1.0,
        widget=forms.NumberInput(attrs={'step':0.1}))

    class Meta:
        model = PredictionGroup
        fields = ['data_format', 'threshold', 'data']

    def clean_data_format(self):
        data_format = self.cleaned_data['data_format']
        if data_format not in ('enter', 'fasta'):
            raise ValidationError(
                'Format is not supported')
        return data_format

    def clean_data(self):
        data = self.cleaned_data['data']
        fmt = self.cleaned_data['data_format']
        lines = data.splitlines()
        if fmt == 'enter':
            seqs = lines
        else:
            info, seqs = read_fasta(lines)
        if len(seqs) > 10:
            raise ValidationError(
                'Number of sequences should not be more than 10!')
        for seq in seqs:
            seq = seq.strip()
            if len(seq) > MAXLEN:
                raise ValidationError(
                    'Sequence length should not be more than 1002!')
            if not is_ok(seq):
                raise ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        self.instance.date = datetime.datetime.now()
        data = self.cleaned_data['data']
        lines = data.splitlines()
        fmt = self.cleaned_data['data_format']
        if fmt == 'enter':
            sequences = lines
        else:
            info, sequences = read_fasta(lines)
        n = len(sequences)
        for i in xrange(n):
            sequences[i] = sequences[i].strip()
        preds = predict_functions.delay(
            sequences)
        preds = preds.get()
        cc = preds[0: n]
        mf = preds[n: n + n]
        bp = preds[2 * n: 3 * n]
        self.instance.save()
        predictions = list()
        for i in range(n):
            if fmt == 'enter':
                pred = Prediction(sequence=sequences[i])
            else:
                pred = Prediction(protein_info=info[i], sequence=sequences[i])
            funcs = cc[i] + mf[i] + bp[i]
            functions = list()
            scores = list()
            for func in funcs:
                pref, go_id, score = func.split('_')
                functions.append(pref + '_' + go_id)
                scores.append(float(score))
            pred.functions = functions
            pred.scores = scores
            pred.group = self.instance
            predictions.append(pred)
        Prediction.objects.bulk_create(predictions)
        return self.instance
