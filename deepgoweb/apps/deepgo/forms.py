from django import forms
from deepgo.models import Prediction, PredictionGroup
import datetime
from django.core.exceptions import ValidationError
from deepgo.utils import (
    read_fasta)
from deepgo.aminoacids import is_ok, MAXLEN
from deepgo.models import Taxonomy
from deepgo import runner


class PredictionForm(forms.ModelForm):

    threshold = forms.FloatField(
        initial=0.3,
        min_value=0.0, max_value=1.0,
        widget=forms.NumberInput(attrs={'step':0.1}))
    model_name = forms.ChoiceField(
        label='Prediction model', initial='deepgoplus',
        widget=forms.RadioSelect)
    use_cnn = forms.BooleanField(
        label='Add CNN component for orphan proteins (no homolog)',
        required=False, initial=False)

    class Meta:
        model = PredictionGroup
        fields = ['model_name', 'use_cnn', 'data_format', 'threshold', 'data']

    def __init__(self, *args, **kwargs):
        super(PredictionForm, self).__init__(*args, **kwargs)
        # Only offer the DeepGO-PlusPlus-Light variants when enabled and their assets exist.
        # MODEL_CHOICES = (deepgoplus, dgpp-light, dgpp-light-mcm).
        choices = [PredictionGroup.MODEL_CHOICES[0]]
        if runner.dgpp_enabled():
            choices.append(PredictionGroup.MODEL_CHOICES[1])
        if runner.dgpp_mcm_enabled():
            choices.append(PredictionGroup.MODEL_CHOICES[2])
        self.fields['model_name'].choices = choices

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
            if not is_ok(seq):
                raise ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        self.instance.date = datetime.datetime.now()
        data = self.cleaned_data['data']
        lines = data.splitlines()
        fmt = self.cleaned_data['data_format']
        model_name = self.cleaned_data.get('model_name', runner.DEEPGOPLUS)
        use_cnn = (model_name == runner.DGPP_LIGHT
                   and self.cleaned_data.get('use_cnn', False))
        if fmt == 'enter':
            sequences = lines
        else:
            info, sequences = read_fasta(lines)
        n = len(sequences)
        for i in range(n):
            sequences[i] = sequences[i].strip()
        preds = runner.run_predictions(sequences, model_name, use_cnn)
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
