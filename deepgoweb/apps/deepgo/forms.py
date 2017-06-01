from django import forms
from deepgo.models import Prediction, PredictionGroup
import datetime
from deepgo.tasks import predict_functions
from django.core.exceptions import ValidationError
from deepgo.utils import go, get_anchestors, is_ok
from deepgo.constants import MAXLEN


def filter_specific(gos):
    go_set = set()
    for go_id in gos:
        go_set.add(go_id)
    for go_id in gos:
        anchestors = get_anchestors(go, go_id)
        anchestors.discard(go_id)
        go_set -= anchestors
    return list(go_set)


def read_fasta(lines):
    seqs = list()
    info = list()
    seq = ''
    inf = ''
    for line in lines:
        line = line.strip()
        if line.startswith('>'):
            if seq != '':
                seqs.append(seq)
                info.append(inf)
                seq = ''
            inf = line[1:]
        else:
            seq += line
    seqs.append(seq)
    info.append(inf)
    return info, seqs


class PredictionForm(forms.ModelForm):

    class Meta:
        model = PredictionGroup
        fields = ['data_format', 'data']

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
        preds = predict_functions.delay(sequences)
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
            pred.functions = filter_specific(cc[i] + mf[i] + bp[i])
            pred.group = self.instance
            predictions.append(pred)
        Prediction.objects.bulk_create(predictions)
        return self.instance
