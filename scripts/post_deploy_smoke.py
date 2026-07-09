#!/usr/bin/env python3
"""Post-deploy smoke tests for DeepGOWeb v2.

Run this against the public URL after every deployment. It intentionally exercises
the reverse proxy, Django, static/templates, REST validation, genome example
downloads, and SPARQL/Fuseki property-function chain.
"""
from __future__ import annotations

import argparse
import html
import http.cookiejar
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DGPP_SEQUENCE = (
    "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVV"
    "HSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAI"
    "WAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHR"
    "HDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQA"
    "LLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
)

SPARQL_QUERY = f"""PREFIX dg: <http://deepgoplus.bio2vec.net/functions#>
PREFIX GO: <http://purl.obolibrary.org/obo/GO_>

SELECT ?ont ?go ?label ?score
{{
 (?ont ?go ?label ?score)
            dg:predict("{DGPP_SEQUENCE}" 0.5 "dgpp-light") .
}}
LIMIT 20
"""


class Smoke:
    def __init__(self, base: str, insecure: bool = False, timeout: int = 300):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl._create_unverified_context() if insecure else None
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPSHandler(context=ctx) if ctx else urllib.request.HTTPSHandler(),
        )

    def url(self, path: str) -> str:
        return self.base + path

    def request(self, path: str, data=None, headers=None, expected=(200,)):
        body = None
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
        elif data is not None:
            body = data
        req = urllib.request.Request(self.url(path), data=body, headers=headers or {})
        attempts = 6 if data is None else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:
                    payload = resp.read()
                    status = resp.status
                    ctype = resp.headers.get("Content-Type", "")
            except urllib.error.HTTPError as exc:
                payload = exc.read()
                status = exc.code
                ctype = exc.headers.get("Content-Type", "")
            if status not in {502, 503, 504} or attempt == attempts - 1:
                break
            time.sleep(5)
        if status not in expected:
            raise AssertionError(f"{path}: HTTP {status}, expected {expected}: {payload[:500]!r}")
        return status, ctype, payload

    def text(self, path: str, expected=(200,)) -> str:
        _, _, payload = self.request(path, expected=expected)
        return payload.decode("utf-8", errors="replace")

    def assert_contains(self, text: str, needle: str, where: str):
        if needle not in text:
            raise AssertionError(f"{where}: missing {needle!r}")

    def run(self):
        checks = [
            ("home", self.check_home),
            ("protein form", self.check_protein_form),
            ("csrf form post", self.check_csrf_post),
            ("changelog", self.check_changelog),
            ("genome examples", self.check_genome_examples),
            ("REST validation", self.check_rest_validation),
            ("SPARQL page", self.check_sparql_page),
            ("SPARQL query", self.check_sparql_query),
            ("static/health/docs", self.check_misc_pages),
        ]
        for name, fn in checks:
            fn()
            print(f"ok - {name}")

    def check_home(self):
        page = self.text("/")
        self.assert_contains(page, "DeepGOWeb", "home")
        self.assert_contains(page, "DeepGO-PlusPlus-Light", "home")

    def check_protein_form(self):
        page = self.text("/deepgo/")
        self.assert_contains(page, "csrfmiddlewaretoken", "protein form")
        self.assert_contains(page, "DeepGOPlus 1.0.18", "protein form")
        self.assert_contains(page, "DeepGO-PlusPlus-Light v2.0-light", "protein form")
        self.assert_contains(page, "the original KAUST-hosted version", "protein form")

    def check_csrf_post(self):
        page = self.text("/deepgo/")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        if not token:
            raise AssertionError("protein form: no CSRF token")
        release = re.search(r'<option value="([^"]+)">DeepGOPlus 1\.0\.18</option>', page)
        dgpp_release = re.search(
            r'<option value="([^"]+)">DeepGO-PlusPlus-Light v2\.0-light</option>', page)
        if not release or not dgpp_release:
            raise AssertionError("protein form: release dropdowns missing expected versions")
        status, _, payload = self.request(
            "/deepgo/",
            data={
                "csrfmiddlewaretoken": token.group(1),
                "predictor": "dgpp-light",
                "release": release.group(1),
                "dgpp_release": dgpp_release.group(1),
                "data_format": "fasta",
                "threshold": "0.5",
                "contract": "on",
                "data": "BADSEQ!",
            },
            headers={
                "Origin": self.base,
                "Referer": self.url("/deepgo/"),
            },
            expected=(200, 302),
        )
        if status == 403 or b"CSRF verification failed" in payload:
            raise AssertionError("protein form POST failed CSRF")

    def check_changelog(self):
        page = self.text("/deepgo/changelog")
        for needle in ("Version 1.0.28", "Version 1.0.0", "Version v2.0-light"):
            self.assert_contains(page, needle, "changelog")
        for forbidden in ("CAFA6", "cafa6", "Expected performance", "rebuild"):
            if forbidden in page:
                raise AssertionError(f"changelog: forbidden text {forbidden!r}")

    def check_genome_examples(self):
        for organism in ("bacteria", "archaea", "eukaryote", "phage"):
            for kind, marker in (("fna", ">"), ("gff3", "##gff-version 3")):
                data = self.text(f"/deepgo/genome/example?organism={organism}&file={kind}")
                self.assert_contains(data, marker, f"genome example {organism}.{kind}")

    def check_rest_validation(self):
        status, _, payload = self.request(
            "/deepgo/api/predict",
            data=json.dumps({
                "version": "latest",
                "predictor": "dgpp-light",
                "data_format": "enter",
                "data": "BADSEQ!",
                "threshold": 0.5,
            }).encode(),
            headers={"Content-Type": "application/json"},
            expected=(400,),
        )
        if b"invalid amino acids" not in payload:
            raise AssertionError(f"REST validation returned unexpected body: {payload[:500]!r}")

    def check_sparql_page(self):
        page = self.text("/deepgo/sparql")
        self.assert_contains(page, "dg:predict", "SPARQL page")
        self.assert_contains(page, "LIMIT 20", "SPARQL page")
        self.assert_contains(page, "$('#query').val(query)", "SPARQL page")

    def check_sparql_query(self):
        status, ctype, payload = self.request(
            "/ds/query",
            data={"query": SPARQL_QUERY},
            headers={"Accept": "application/sparql-results+json"},
            expected=(200,),
        )
        root = json.loads(payload.decode("utf-8"))
        bindings = root.get("results", {}).get("bindings", [])
        if not bindings:
            raise AssertionError("SPARQL dg:predict returned no bindings")
        first = bindings[0]
        if "go" not in first or "score" not in first:
            raise AssertionError(f"SPARQL binding missing go/score: {first!r}")

    def check_misc_pages(self):
        for path, needle in (
            ("/deepgo/genome", "DeepGO-GSPA"),
            ("/doc/", "SPARQL"),
            ("/contacts", "Robert"),
        ):
            self.assert_contains(self.text(path), needle, path)
        self.request("/healthcheck", expected=(200,))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://deepgo.bio2vec.net")
    ap.add_argument("--insecure", action="store_true", help="disable TLS verification")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)
    Smoke(args.base_url, insecure=args.insecure, timeout=args.timeout).run()


if __name__ == "__main__":
    main()
