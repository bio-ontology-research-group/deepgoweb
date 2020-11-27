from deepgo.models import Prediction, PredictionGroup, Release
from rest_framework import serializers
from deepgo.utils import (
    read_fasta)
from deepgo.aminoacids import is_ok, MAXLEN
import datetime
from deepgo.tasks import predict_functions
        

class PredictionSerializer(serializers.ModelSerializer):

    functions = serializers.SerializerMethodField()
    
    class Meta:
        model = Prediction
        fields = ['protein_info', 'sequence', 'functions']
    
    def get_functions(self, obj):
        return obj.get_functions()
    
class PredictionGroupSerializer(serializers.ModelSerializer):

    release_version = serializers.CharField(max_length=15)
    predictions = PredictionSerializer(many=True, read_only=True)
    
    class Meta:
        model = PredictionGroup
        fields = ['uuid', 'release_version', 'data_format', 'data', 'threshold', 'predictions']
        extra_kwargs = {
            'data': {'write_only': True}}

    def validate_release_version(self, version):
        queryset = Release.objects.filter(version=version)
        if not queryset.exists():
            raise serializers.ValidationError('Version does not exist')
        return version
    
    def validate(self, data):
        if 'data_format' not in data:
            raise serializers.ValidationError(
                'data_format field is required!'
            )

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
            if not is_ok(seq):
                raise serializers.ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        rel_ver = self.validated_data.pop('release_version')
        self.instance = super(PredictionGroupSerializer, self).save()
        fmt = self.validated_data['data_format']
        data = self.validated_data['data']
        release = Release.objects.get(version=rel_ver)
        self.instance.release = release
        lines = data.splitlines()
        if fmt == 'enter':
            sequences = lines
        else:
            info, sequences = read_fasta(lines)
        n = len(sequences)
        for i in range(n):
            sequences[i] = sequences[i].strip()
        preds = predict_functions.delay(
            release.pk,
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
            pred.group = self.instance
            pred.similar_proteins = similar_proteins
            pred.similar_scores = similar_scores
            predictions.append(pred)
        Prediction.objects.bulk_create(predictions)
        return self.instance
