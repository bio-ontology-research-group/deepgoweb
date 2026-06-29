"""Seed the example PredictionGroup that the form + docs link to.

The prediction page and documentation show "an example result" at a fixed UUID
(deepgo.constants.EXAMPLE_UUID). On a fresh database that row does not exist, so
the link 404s. This command creates it by running the current DeepGOPlus model on
the AAKB1 (P80386) example sequence, so the linked result is real and up to date.
Run once after loadrelease (e.g. in the deploy/entrypoint), idempotent.
"""
from django.core.management.base import BaseCommand, CommandError
from deepgo.models import Release, PredictionGroup, Prediction
from deepgo.constants import EXAMPLE_UUID
from deepgo.tasks import predict_functions

# AAKB1_RAT (UniProt P80386) — the FASTA example shown on the prediction form.
AAKB1 = (
    'MGNTSSERAALERQAGHKTPRRDSSGGTKDGDRPKILMDSPEDADIFHTEEMKAPEKEEF'
    'LAWQHDLEVNEKAPAQARPTVFRWTGGGKEVYLSGSFNNWSKLPLTRSQNNFVAILDLPE'
    'GEHQYKFFVDGQWTHDPSEPIVTSQLGTVNNIIQVKKTDFEVFDALMVDSQKCSDVSELS'
    'SSPPGPYHQEPYISKPEERFKAPPILPPHLLQVILNKDTGISCDPALLPEPNHVMLNHLY'
    'ALSIKDGVMVLSATHRYKKKYVTTLLYKPI'
)


class Command(BaseCommand):
    help = 'Seed the example PredictionGroup linked from the prediction form and docs.'

    def handle(self, *args, **options):
        if PredictionGroup.objects.filter(uuid=EXAMPLE_UUID).exists():
            self.stdout.write('example already seeded')
            return
        release = (Release.objects.filter(predictor_type='deepgoplus')
                   .order_by('-pk').first())
        if release is None:
            raise CommandError('no DeepGOPlus Release; run loadrelease first')
        # Run the predictor synchronously (no celery needed for a one-off seed).
        preds = predict_functions(release.pk, [AAKB1])
        funcs, sim = preds[0]
        group = PredictionGroup.objects.create(
            uuid=EXAMPLE_UUID, predictor='deepgoplus', release=release,
            data=AAKB1, data_format='fasta', threshold=0.3, contract=True)
        Prediction.objects.create(
            group=group, sequence=AAKB1, protein_info='sp|P80386|AAKB1_RAT',
            functions=list(funcs.keys()),
            scores=[float(s) for s in funcs.values()],
            similar_proteins=list(sim.keys()),
            similar_scores=[float(s) for s in sim.values()])
        self.stdout.write(self.style.SUCCESS(f'seeded example {EXAMPLE_UUID}'))
