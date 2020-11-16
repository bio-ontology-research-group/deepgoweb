from django import forms
from deepgo.models import Prediction, PredictionGroup
import datetime
from deepgo.tasks import predict_functions
from django.core.exceptions import ValidationError
from deepgo.utils import (
    read_fasta)
from deepgo.aminoacids import is_ok, MAXLEN
from deepgo.models import Taxonomy


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
        if len(seqs) > 1000:
            raise ValidationError(
                'Number of sequences should not be more than 1000!')
        for seq in seqs:
            seq = seq.strip()
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
        for i in range(n):
            sequences[i] = sequences[i].strip()
        preds = predict_functions.delay(
            sequences)
        preds = preds.get()
        self.instance.save()
        predictions = list()
        for i in range(n):
            if fmt == 'enter':
                pred = Prediction(sequence=sequences[i])
            else:
                pred = Prediction(protein_info=info[i], sequence=sequences[i])
            funcs, sim_prots = preds[i]
            functions = list()
            scores = list()
            similar_proteins = list()
            similar_scores = list()
            for go_id, score in funcs.items():
                functions.append(go_id)
                scores.append(float(score))
            for prot_id, score in sim_prots.items():
                similar_proteins.append(prot_id)
                similar_scores.append(float(score))
            pred.functions = functions
            pred.scores = scores
            pred.similar_proteins = similar_proteins
            pred.similar_scores = similar_scores
            pred.group = self.instance
            predictions.append(pred)
        Prediction.objects.bulk_create(predictions)
        return self.instance

    
class DownloadForm(forms.Form):
    organism = forms.CharField(strip=True)
    org_id = forms.IntegerField(widget=forms.HiddenInput())
    
    def clean_org_id(self):
        org_id = self.cleaned_data['org_id']
        try:
            Taxonomy.objects.get(id=org_id)
        except Taxonomy.DoesNotExist:
            raise forms.ValidationError('Organism does not exist!')
        return org_id
