from deepgo.models import Prediction, PredictionGroup
from rest_framework import serializers
from deepgo.utils import (
    is_ok, read_fasta, filter_specific)
from deepgo.constants import MAXLEN
import datetime
from deepgo.tasks import predict_functions


class PredictionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Prediction
        fields = ['sequence', 'functions', 'scores']

        
class PredictionGroupSerializer(serializers.ModelSerializer):

    predictions = PredictionSerializer(many=True, read_only=True)
    
    class Meta:
        model = PredictionGroup
        fields = ['id', 'data_format', 'data', 'threshold', 'predictions']
        extra_kwargs = {
            'data': {'write_only': True}}

    def validate(self, data):
        fmt = data['data_format']
        if fmt not in ('enter', 'fasta'):
            raise serializers.ValidationError(
                'Format is not supported')
        seq_data = data['data']
        lines = seq_data.splitlines()
        if fmt == 'enter':
            seqs = lines
        else:
            info, seqs = read_fasta(lines)
        if len(seqs) > 10:
            raise serializers.ValidationError(
                'Number of sequences should not be more than 10!')
        for seq in seqs:
            seq = seq.strip()
            if len(seq) > MAXLEN:
                raise serializers.ValidationError(
                    'Sequence length should not be more than 1002!')
            if not is_ok(seq):
                raise serializers.ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        fmt = self.validated_data['data_format']
        data = self.validated_data['data']
        self.instance = PredictionGroup(
            data_format=fmt,
            data=data,
            date=datetime.datetime.now(),
            threshold=self.validated_data['threshold'])
        lines = data.splitlines()
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
