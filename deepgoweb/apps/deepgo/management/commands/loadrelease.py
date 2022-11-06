from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import gzip
import logging
from deepgo.utils import acc2id
from deepgo.models import Release
import json
logging.basicConfig(level=logging.INFO)
ROOT = "/opt-data/extracted/"

class Command(BaseCommand):
    help = 'Load proteins from UniProt FASTA file (gzipped)'

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('version', type=str)
    
    def handle(self, *args, **options):
        version = options['version']
        version_path = ROOT + version
        if not os.path.exists(version_path):
            raise CommandError('no such file')

        try:
            with open(version_path + "/RELEASE.html", "r") as f:
                notes = f.read()

            with open(version_path + "/metadata/last_release.json", "r") as f:
                last_release = json.load(f)
                alphas = last_release["alphas"]
                alpha_bp = alphas["bp"]
                alpha_mf = alphas["mf"]
                alpha_cc = alphas["cc"]


            release = Release(
                version=version,
                notes=notes,
                data_root=version_path,
                alpha_bp=alpha_bp,
                alpha_mf=alpha_mf,
                alpha_cc=alpha_cc
            )

            release.data_root = version_path
            release.save()
                    
        except Exception as e:
            raise CommandError(str(e))    
