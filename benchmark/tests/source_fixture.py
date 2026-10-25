"""Rebuild the selected observation fixture without a stored replay archive."""
import json
from pathlib import Path

from yugioh_benchmark.native_json import convert_json, parse_export
from yugioh_benchmark.replay import write_bundle


ROOT = Path(__file__).resolve().parents[1]


def fixture_replay():
    source = json.loads((ROOT / 'benchmarks/sources.json').read_text(encoding='utf-8'))['sources'][0]
    data = parse_export((ROOT / source['fixture']).read_text(encoding='utf-8'))
    return convert_json(data, source['source_url'], source['retrieved_at'])


def write_fixture_bundle(directory):
    write_bundle(fixture_replay(), directory)
    return directory
