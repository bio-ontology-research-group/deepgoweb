"""Ingest CAFA evaluation metrics for a Release.

Reproducibility: F-max (and the per-aspect / per-knowledge-class breakdown) is
computed OFFLINE — the gspa ``cafa6_recon`` harness + the official cafaeval on the
ws server — and emitted as a JSON. This command loads that JSON into CafaMetrics
rows so the web app can display each version's expected performance without doing
any heavy computation itself.

JSON schema:
  {
    "protocol": "cafa6-recon",            # optional, default 'cafa6-recon'
    "metrics": [
      {"knowledge_class": "no_knowledge", "fmax": 0.49,
       "fmax_mf": 0.59, "fmax_bp": 0.30, "fmax_cc": 0.54,
       "coverage": 0.66, "notes": "..."},
      ...
    ]
  }

Usage:  manage.py loadmetrics <version> <metrics.json>
"""
import json
from django.core.management.base import BaseCommand, CommandError
from deepgo.models import Release, CafaMetrics


class Command(BaseCommand):
    help = 'Load CAFA metrics (from a JSON emitted by the cafa6_recon harness) for a Release.'

    def add_arguments(self, parser):
        parser.add_argument('version', type=str, help='Release.version to attach metrics to.')
        parser.add_argument('json_path', type=str, help='Path to the metrics JSON.')

    def handle(self, *args, **options):
        try:
            release = Release.objects.get(version=options['version'])
        except Release.DoesNotExist:
            raise CommandError(f"no Release with version '{options['version']}' "
                               f"(register it first with loadrelease)")
        with open(options['json_path']) as f:
            payload = json.load(f)
        protocol = payload.get('protocol', 'cafa6-recon')
        rows = payload.get('metrics', [])
        if not rows:
            raise CommandError('metrics JSON has no "metrics" array')
        n = 0
        for r in rows:
            CafaMetrics.objects.update_or_create(
                release=release,
                knowledge_class=r['knowledge_class'],
                protocol=protocol,
                defaults=dict(
                    fmax=r['fmax'],
                    fmax_mf=r.get('fmax_mf'),
                    fmax_bp=r.get('fmax_bp'),
                    fmax_cc=r.get('fmax_cc'),
                    coverage=r.get('coverage'),
                    notes=r.get('notes', ''),
                ),
            )
            n += 1
        self.stdout.write(self.style.SUCCESS(
            f'loaded {n} CafaMetrics row(s) for {release.version} (protocol={protocol})'))
