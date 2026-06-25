from deepgo.models import Prediction, PredictionGroup, Release
from rest_framework import serializers
from deepgo.utils import (
    read_fasta)
from deepgo.aminoacids import is_ok, MAXLEN
import datetime
from deepgo.tasks import predict_functions, predict_functions_dgpp
        

class PredictionSerializer(serializers.ModelSerializer):

    functions = serializers.SerializerMethodField()
    
    class Meta:
        model = Prediction
        fields = ['protein_info', 'sequence', 'functions']
    
    def get_functions(self, obj):
        # API returns the full propagated set (obsolete terms resolved), not the
        # contracted view used for the HTML page.
        return obj.get_functions(contract=False)
    
class PredictionGroupSerializer(serializers.ModelSerializer):

    version = serializers.CharField(max_length=15)
    predictions = PredictionSerializer(many=True, read_only=True)
    
    class Meta:
        model = PredictionGroup
        fields = ['uuid', 'version', 'data_format', 'data', 'threshold', 'predictions']
        extra_kwargs = {
            'data': {'write_only': True}}

    def validate_version(self, version):
        if version == 'latest':
            return version
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
        if len(seqs) > 100:
            raise serializers.ValidationError(
                'Number of sequences should not be more than 100!')
        for seq in seqs:
            seq = seq.strip()
            if not is_ok(seq):
                raise serializers.ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        rel_ver = self.validated_data.pop('version')
        self.instance = super(PredictionGroupSerializer, self).save()
        fmt = self.validated_data['data_format']
        data = self.validated_data['data']
        if rel_ver == 'latest':
            release = Release.objects.order_by('-pk').first()
        else:
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


class PredictionGroupV2Serializer(serializers.ModelSerializer):
    """Predictor-aware API (backwards-compatible *addition* — the original
    ``PredictionGroupSerializer`` / ``api/create`` are unchanged).

    Accepts an extra ``predictor`` field (default ``deepgoplus`` so old clients
    that don't send it get the legacy behaviour). When ``predictor`` is
    ``dgpp-light`` it runs the DeepGO-PlusPlus-Light CPU cascade and additionally
    returns each component's own top predictions (ProteInfer, STRING-Net, the
    hierarchy-aware CNN, ESM2-kNN, DIAMOND, ...) under ``components`` — the
    per-protein substreams the SPARQL ``dg:components`` function exposes.
    """
    version = serializers.CharField(max_length=15)
    predictor = serializers.ChoiceField(
        choices=PredictionGroup.PREDICTOR_CHOICES, default='deepgoplus')
    predictions = PredictionSerializer(many=True, read_only=True)
    components = serializers.SerializerMethodField()

    class Meta:
        model = PredictionGroup
        fields = ['uuid', 'version', 'predictor', 'data_format', 'data',
                  'threshold', 'predictions', 'components']
        extra_kwargs = {
            'data': {'write_only': True}}

    def get_components(self, obj):
        # Per-protein {component_label: [[go_id, name, score], ...]} (dgpp-light
        # only; empty list otherwise).
        return obj.component_predictions or []

    def validate_version(self, version):
        if version == 'latest':
            return version
        queryset = Release.objects.filter(version=version)
        if not queryset.exists():
            raise serializers.ValidationError('Version does not exist')
        return version

    def validate(self, data):
        if 'data_format' not in data:
            raise serializers.ValidationError('data_format field is required!')
        fmt = data['data_format']
        if fmt not in ('enter', 'fasta'):
            raise serializers.ValidationError('Format is not supported')
        lines = data['data'].splitlines()
        if fmt == 'enter':
            seqs = lines
        else:
            info, seqs = read_fasta(lines)
        if len(seqs) > 100:
            raise serializers.ValidationError(
                'Number of sequences should not be more than 100!')
        for seq in seqs:
            if not is_ok(seq.strip()):
                raise serializers.ValidationError(
                    'Sequence contains invalid amino acids!')
        return data

    def save(self):
        predictor = self.validated_data.get('predictor', 'deepgoplus')
        rel_ver = self.validated_data.pop('version')
        # super().save() creates the PredictionGroup (incl. the predictor field).
        self.instance = super(PredictionGroupV2Serializer, self).save()
        fmt = self.validated_data['data_format']
        data = self.validated_data['data']
        if rel_ver == 'latest':
            release = Release.objects.order_by('-pk').first()
        else:
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
        if predictor == 'dgpp-light':
            preds, components = predict_functions_dgpp.delay(sequences, 'mcm').get()
            self.instance.component_predictions = components
        else:
            preds = predict_functions.delay(release.pk, sequences).get()
        self.instance.save()
        predictions = list()
        for i in range(n):
            if fmt == 'enter':
                pred = Prediction(sequence=sequences[i])
            else:
                pred = Prediction(protein_info=info[i], sequence=sequences[i])
            funcs, sim_prots = preds[i]
            functions, scores = list(), list()
            similar_proteins, similar_scores = list(), list()
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
