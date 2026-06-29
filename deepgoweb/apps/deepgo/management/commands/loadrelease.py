from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import logging
from deepgo.models import Release
import json
logging.basicConfig(level=logging.INFO)
ROOT = "/opt-data/extracted/"


class Command(BaseCommand):
    help = ('Register a versioned model Release. DeepGOPlus reads RELEASE.html + '
            'metadata/last_release.json from /opt-data/extracted/<version>; '
            'DG++Light (--predictor dgpp-light) registers a versioned dgpp asset '
            'bundle (default <DGPP_ASSETS>/<version>).')

    def add_arguments(self, parser):
        parser.add_argument('version', type=str)
        parser.add_argument(
            '--predictor', type=str, default='deepgoplus',
            choices=['deepgoplus', 'dgpp-light'],
            help='Which predictor this version belongs to (default deepgoplus).')
        parser.add_argument(
            '--data-root', type=str, default='',
            help='Asset directory for this version. Defaults: deepgoplus -> '
                 '/opt-data/extracted/<version>; dgpp-light -> <DGPP_ASSETS>/<version>.')
        parser.add_argument(
            '--notes', type=str, default='',
            help='Inline release notes (HTML). If omitted, RELEASE.html in the '
                 'data-root is used when present.')

    def handle(self, *args, **options):
        version = options['version']
        predictor = options['predictor']
        version_path = options['data_root']
        if not version_path:
            if predictor == 'deepgoplus':
                version_path = ROOT + version
            else:
                assets = settings.DGPP_LIGHT.get('ASSETS', '')
                version_path = os.path.join(assets, version)
        if not os.path.exists(version_path):
            raise CommandError(f'no such data-root: {version_path}')

        notes = options['notes']
        if not notes:
            rel_html = os.path.join(version_path, 'RELEASE.html')
            if os.path.exists(rel_html):
                with open(rel_html) as f:
                    notes = f.read()

        # DeepGOPlus carries per-aspect DIAMOND/CNN blend weights; dgpp-light does not.
        alpha = {'bp': 0.59, 'mf': 0.55, 'cc': 0.46}
        meta = os.path.join(version_path, 'metadata', 'last_release.json')
        if predictor == 'deepgoplus' and os.path.exists(meta):
            with open(meta) as f:
                alpha = json.load(f)['alphas']

        rel, created = Release.objects.update_or_create(
            version=version,
            defaults=dict(
                predictor_type=predictor,
                notes=notes,
                data_root=version_path,
                alpha_bp=alpha['bp'], alpha_mf=alpha['mf'], alpha_cc=alpha['cc'],
            ),
        )
        action = 'created' if created else 'updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {predictor} Release {version} (pk={rel.pk}) -> {version_path}'))
