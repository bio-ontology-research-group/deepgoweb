from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import gzip
import logging
from deepgo.utils import acc2id
from deepgo.models import Annotation

logging.basicConfig(level=logging.INFO)


class Command(BaseCommand):
    help = 'Load proteins from UniProt FASTA file (gzipped)'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str)
    
    def handle(self, *args, **options):
        filename = options['filename']
        if not os.path.exists(filename):
            raise CommandError('no such file')

        try:
            with gzip.open(filename, 'rt') as f:
                annots = []
                for line in f:
                    it = line.strip().split('\t')
                    _, acc_id, pro_id = it[0].split('|')
                    id = acc2id(acc_id)
                    for item in it[1:]:
                        go_id, score = item.split('|')
                        go_id = int(go_id.split(':')[1])
                        score = int(float(score) * 100)
                        annots.append(
                            Annotation(
                                protein_id=id, go_id=go_id,
                                score=score))
                        if len(annots) >= 1000000:
                            Annotation.objects.bulk_create(
                                annots, ignore_conflicts=True)
                            annots = []
                if len(annots) > 0:
                    Annotation.objects.bulk_create(
                        annots, ignore_conflicts=True)
                            
                    
        except Exception as e:
            print(acc_id, pro_id)
            raise CommandError(str(e))    
