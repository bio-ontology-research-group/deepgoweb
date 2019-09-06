from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import gzip
import logging
from deepgo.utils import acc2id
from deepgo.models import Taxonomy, Protein

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
                for line in f:
                    # Ignore sequence
                    if line[0] != '>':
                        continue
                    line = line[1:].strip().split('=')
                    it = line[0].split(' ')
                    pro = it[0].split('|')
                    pro_id = pro[2]
                    acc_id = pro[1]
                    id = acc2id(acc_id)
                    reviewed = pro[0] == 'sp'
                    name = ' '.join(it[1:-1])
                    it = line[1].split(' ')
                    tax_name = ' '.join(it[:-1])
                    it = line[2].split(' ')
                    tax_id = int(it[0])
                    gene_name = None
                    if it[1] == 'GN':
                        it = line[3].split(' ')
                        gene_name = it[0]
                    Taxonomy.objects.get_or_create(id=tax_id, name=tax_name)
                    protein = Protein(
                        id=id,
                        acc_id=acc_id,
                        pro_id=pro_id,
                        name=name,
                        reviewed=reviewed,
                        gene=gene_name,
                        taxon_id=tax_id,
                    )
                    protein.save()
                    
        except Exception as e:
            print(id, acc_id, pro_id)
            raise CommandError(str(e))    
