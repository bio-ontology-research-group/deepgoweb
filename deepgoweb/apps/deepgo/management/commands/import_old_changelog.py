"""Import the historical DeepGOPlus changelog into Release.notes.

The original DeepGOWeb changelog is served as HTML. This command reads that page,
extracts each "Version X" block, and stores the public release prose/table as
HTML notes on DeepGOPlus Release rows. It is idempotent and intentionally stores
the public text, not benchmark-side metadata.
"""
from html import escape
from html.parser import HTMLParser
import re
import urllib.request

from django.core.management.base import BaseCommand
from django.utils import timezone

from deepgo.models import Release


DEFAULT_URL = 'https://deepgo.cbrc.kaust.edu.sa/deepgo/changelog'
DEFAULT_DATA_ROOT = '/opt-data/extracted/'


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'h1', 'h2', 'h3', 'h4', 'p', 'tr', 'li'}:
            self.parts.append('\n')
        elif tag in {'td', 'th'}:
            self.parts.append('\t')

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        lines = []
        for raw in ''.join(self.parts).splitlines():
            line = re.sub(r'[ \t]+', ' ', raw).strip()
            if line:
                lines.append(line)
        return lines


def _parse_blocks(lines):
    blocks = []
    current = None
    for line in lines:
        m = re.match(r'^Version\s+([0-9.]+)$', line)
        if m:
            if current:
                blocks.append(current)
            current = {'version': m.group(1), 'lines': []}
        elif current:
            if line.startswith('DeepGOWeb by '):
                break
            current['lines'].append(line)
    if current:
        blocks.append(current)
    return blocks


def _date_from(lines):
    for line in lines:
        m = re.match(r'^Date:\s*\[([0-9-]+)\]$', line)
        if m:
            return timezone.datetime.fromisoformat(m.group(1)).replace(
                tzinfo=timezone.get_current_timezone())
    return timezone.now()


def _notes_html(lines):
    body = [line for line in lines if not line.startswith('Date:')]
    merged = []
    i = 0
    while i < len(body):
        line = body[i]
        if (i + 1 < len(body)
                and line.endswith('using the Gene Ontology')
                and body[i + 1].startswith('# released ')):
            merged.append(line + ' released ' + body[i + 1][11:])
            i += 2
            continue
        if (i + 1 < len(body)
                and line.endswith('using the Gene Ontology')
                and body[i + 1].startswith('released ')):
            merged.append(line + ' ' + body[i + 1])
            i += 2
            continue
        merged.append(line)
        i += 1
    body = merged
    if not body:
        return ''
    parts = []
    i = 0
    while i < len(body):
        line = body[i]
        if line.startswith('The obtained results are the following') and i + 3 < len(body):
            parts.append('<p>The obtained results are the following:</p>')
            parts.append('<table class="table table-sm table-bordered w-auto">')
            parts.append('<thead><tr><th></th><th>Fmax</th><th>Smin</th><th>AUPR</th></tr></thead>')
            parts.append('<tbody>')
            if i + 1 < len(body) and body[i + 1] == 'Fmax Smin AUPR':
                i += 2
            else:
                i += 1
            for _ in range(3):
                cols = body[i].split()
                if len(cols) >= 4:
                    parts.append(
                        '<tr><th>{}</th><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                            escape(cols[0]), escape(cols[1]), escape(cols[2]), escape(cols[3])))
                i += 1
            parts.append('</tbody></table>')
            continue
        parts.append('<p>{}</p>'.format(escape(line)))
        i += 1
    return '\n'.join(parts)


class Command(BaseCommand):
    help = 'Import historical DeepGOPlus releases from the original DeepGOWeb changelog.'

    def add_arguments(self, parser):
        parser.add_argument('--url', default=DEFAULT_URL)
        parser.add_argument('--data-root-base', default=DEFAULT_DATA_ROOT)

    def handle(self, *args, **options):
        with urllib.request.urlopen(options['url'], timeout=60) as response:
            html = response.read().decode('utf-8', errors='replace')
        parser = _TextParser()
        parser.feed(html)
        blocks = _parse_blocks(parser.text())
        count = 0
        for block in blocks:
            version = block['version']
            Release.objects.update_or_create(
                version=version,
                defaults=dict(
                    predictor_type='deepgoplus',
                    notes=_notes_html(block['lines']),
                    date=_date_from(block['lines']),
                    data_root=options['data_root_base'].rstrip('/') + '/' + version,
                ),
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(
            f'imported {count} historical DeepGOPlus changelog release(s)'))
