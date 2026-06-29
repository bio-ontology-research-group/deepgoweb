from django import forms
from django.utils.safestring import mark_safe
from deepgo.models import GenomeJob, Prediction, PredictionGroup, Release
import datetime
from django.conf import settings
from deepgo.tasks import predict_functions, predict_functions_dgpp
from django.core.exceptions import ValidationError
from deepgo.utils import (
    read_fasta)
from deepgo.aminoacids import is_ok, MAXLEN

# Web-upload size cap for the genome tab. Genome-scale inputs are far bigger than
# the per-protein paste box (a bacterial genome FASTA is a few MB); keep a sane
# ceiling so a stray huge upload can't fill the DB. The gspa service has its own,
# higher cap (GSPA_MAX_UPLOAD_BYTES).
GENOME_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class PredictionForm(forms.ModelForm):

    # One version dropdown per predictor (shown/hidden by predictor; see form.html).
    # ``release`` ultimately lands on PredictionGroup.release for either predictor.
    release = forms.ModelChoiceField(
        Release.objects.filter(predictor_type='deepgoplus').order_by('-pk'),
        required=False, empty_label=None,
        label=mark_safe('Release version (see <a href="/deepgo/changelog">changelog</a>)'))

    dgpp_release = forms.ModelChoiceField(
        Release.objects.filter(predictor_type='dgpp-light').order_by('-pk'),
        required=False, empty_label=None,
        label=mark_safe('DG++Light version (see <a href="/deepgo/changelog">changelog</a>)'))

    threshold = forms.FloatField(
        initial=0.3,
        min_value=0.0, max_value=1.0,
        widget=forms.NumberInput(attrs={'step':0.1}),
        label='Prediction threshold')

    predictor = forms.ChoiceField(
        choices=PredictionGroup.PREDICTOR_CHOICES, initial='deepgoplus',
        label='Prediction model')

    contract = forms.BooleanField(
        initial=True, required=False,
        label='Show only the most specific terms (hide redundant ancestors '
              'above the threshold)')

    class Meta:
        model = PredictionGroup
        fields = ['predictor', 'release', 'data_format', 'threshold',
                  'contract', 'data']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data'].label = 'Sequences'
        # Offer DeepGO-PlusPlus-Light only when it is enabled AND at least one
        # versioned dgpp-light Release has been archived (loadrelease + loadmetrics).
        cfg = getattr(settings, 'DGPP_LIGHT', None)
        has_dgpp = (bool(cfg and cfg.get('ENABLED'))
                    and Release.objects.filter(predictor_type='dgpp-light').exists())
        if not has_dgpp:
            self.fields['predictor'].choices = [PredictionGroup.PREDICTOR_CHOICES[0]]
            self.fields.pop('dgpp_release', None)
        self.fields['data_format'].label = 'Input Format (FASTA/Raw)'

    def clean(self):
        cleaned = super().clean()
        predictor = cleaned.get('predictor', 'deepgoplus')
        if predictor == 'dgpp-light':
            if not cleaned.get('dgpp_release'):
                raise ValidationError('Select a DG++Light version.')
        elif not cleaned.get('release'):
            raise ValidationError('Select a release version.')
        return cleaned

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
        if fmt == 'enter':
            sequences = lines
        else:
            info, sequences = read_fasta(lines)
        n = len(sequences)
        for i in range(n):
            sequences[i] = sequences[i].strip()
        predictor = self.cleaned_data.get('predictor', 'deepgoplus')
        if predictor == 'dgpp-light':
            # DeepGO-PlusPlus-Light: the selected version's archived bundle; also
            # returns each component's own top predictions for display.
            release = self.cleaned_data['dgpp_release']
            self.instance.release = release
            preds, components = predict_functions_dgpp.delay(
                release.pk, sequences, 'mcm').get()
            self.instance.component_predictions = components
        else:
            release = self.cleaned_data['release']
            self.instance.release = release
            preds = predict_functions.delay(release.pk, sequences).get()
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


class GenomeForm(forms.ModelForm):
    """Upload form for the DeepGO-GSPA genome-scale tab. Takes a genome (or
    metagenome) FASTA plus an optional GFF3, or a pre-called protein FASTA, and
    the genome-scale options. File contents are read into the :class:`GenomeJob`
    text fields so the worker can pick them up; the actual annotation runs async
    against the gspa service (see :func:`deepgo.tasks.annotate_genome`).

    The organism is **inferred**, not assumed: by default the domain is read off
    the predicted functions via the GO taxon constraints (Asaad-style — the most
    confident predictions place the proteome in the domain whose constraints they
    violate least), and the inferred domain is shown on the result page and used
    for taxon-consistency enforcement. A manual override is offered for the rare
    case where you already know the organism. The base predictor is fixed to
    DeepGO-PlusPlus-Light (the CPU model this deployment serves)."""

    DOMAIN_CHOICES = [
        ('auto', 'Infer from the predicted functions (recommended)'),
        ('bacteria', 'Bacteria (override)'),
        ('archaea', 'Archaea (override)'),
        ('eukaryote', 'Eukaryote (override)'),
        ('virus', 'Virus (override)'),
    ]

    genome_file = forms.FileField(
        required=False, label='Genome / metagenome FASTA',
        help_text='Nucleotide FASTA, one contig per record (a chromosome, a MAG, '
                  'or many contigs). This is the primary input.')
    gff3_file = forms.FileField(
        required=False, label='Gene annotation (GFF3, optional)',
        help_text='If supplied, the CDS in it are translated and mapped to their '
                  'contig instead of calling genes. Produce one with Prodigal, '
                  'Prokka or Bakta. Omit it and genes are called automatically.')
    proteins_file = forms.FileField(
        required=False, label='Protein FASTA (alternative to a genome)',
        help_text='Already have predicted proteins? Upload them instead of a '
                  'genome; they are annotated on a single synthetic contig.')

    domain = forms.ChoiceField(
        choices=DOMAIN_CHOICES, initial='auto', label='Organism domain',
        help_text='Leave on "Infer" and the domain is read off the predictions: '
                  'the high-confidence GO terms are tested against the NCBI taxon '
                  'constraints, and the proteome is placed in the domain whose '
                  'constraints they violate least (Asaad-style). The inferred '
                  'domain is shown with its evidence and used for taxon-consistency '
                  'enforcement. Override only if you already know the organism.')

    class Meta:
        model = GenomeJob
        fields = ['metrics_scope', 'mag', 'enforce_consistency',
                  'consistency_mode', 'enforce_completeness', 'enforce_coherence',
                  'provenance']
        labels = {
            'metrics_scope': 'Genome-scale metrics',
            'mag': 'Metagenome-assembled genome (MAG)',
            'enforce_consistency': 'Enforce taxon consistency',
            'consistency_mode': 'Action on inconsistent terms',
            'enforce_completeness': 'Impute missing essential functions',
            'enforce_coherence': 'Repair coherence',
            'provenance': 'Record provenance',
        }
        help_texts = {
            'metrics_scope': 'Per contig is the right unit for a metagenome or '
                'multi-replicon assembly — a chromosome, a plasmid and a phage '
                'score separately, which pooling would hide.',
            'mag': 'Relaxes quality thresholds for a fragmented / incomplete bin.',
            'enforce_consistency': 'Run the SAT4J taxon-constraint pass: GO terms '
                'that cannot occur in the organism (NCBI taxon constraints) are '
                'acted on. Vendored from the genome-scale-pfp-adjust constraints.',
            'consistency_mode': 'remove deletes the term; downrank halves its '
                'score; flag only marks it; minimal-flip drops the minimum-cost '
                'set so the surviving annotations are jointly consistent.',
            'enforce_completeness': 'Each missing essential function is promoted '
                'onto the protein with the strongest near-ancestor evidence and '
                'marked imputed — never fabricated when there is no evidence.',
            'enforce_coherence': 'Fix obligate heteromeric-complex singletons and '
                'missing has_part partners. Advanced: runs the ELK reasoner, so it '
                'is slower.',
            'provenance': 'Record how every annotation was assigned — the '
                'originating predictor and any enforcement action — and emit the '
                'enforcement-actions log.',
        }

    def _read(self, key):
        """Read an uploaded file (size-capped) and return (filename, text)."""
        f = self.cleaned_data.get(key)
        if not f:
            return '', ''
        if f.size > GENOME_MAX_UPLOAD_BYTES:
            raise ValidationError(
                f'{f.name} is too large (limit '
                f'{GENOME_MAX_UPLOAD_BYTES // (1024 * 1024)} MB).')
        return f.name, f.read().decode('utf-8', errors='replace')

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('genome_file') and not cleaned.get('proteins_file'):
            raise ValidationError(
                'Provide a genome FASTA (or a protein FASTA).')
        return cleaned

    def save(self, commit=True):
        job = super().save(commit=False)
        job.genome_filename, job.genome_data = self._read('genome_file')
        job.gff3_filename, job.gff3_data = self._read('gff3_file')
        job.proteins_filename, job.proteins_data = self._read('proteins_file')
        # One domain control drives both the essential-function profile (kingdom)
        # and the asserted taxon for consistency enforcement.
        domain = self.cleaned_data.get('domain', 'auto')
        job.kingdom = '' if domain == 'auto' else domain
        job.taxon = '' if domain == 'auto' else domain
        job.predictor = 'light'      # the CPU model this deployment serves
        job.status = 'pending'
        if commit:
            job.save()
        return job

    
