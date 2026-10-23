import argparse
import json
from pathlib import Path

from .candidates import decision_candidates
from .inputs import read_bytes, read_text
from .replay import load_bundle, write_bundle


def summary(replay):
    counts = {}
    for event in replay['events']:
        counts[event['kind']] = counts.get(event['kind'], 0) + 1
    return {'id': replay['id'], 'events': len(replay['events']),
            'games': max(e['game'] for e in replay['events']),
            'kinds': counts, 'coverage': replay['coverage']}


def main():
    parser = argparse.ArgumentParser(description='Import native Duelingbook JSON and score reviewed agentic KPIs')
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('evaluate', help='Run identical reviewed checkpoints through a metered model transport and real harness')
    command.add_argument('dataset', type=Path)
    command.add_argument('--output', required=True, type=Path)
    command.add_argument('--models', required=True, nargs='+')
    command.add_argument('--referee-model', required=True)
    command.add_argument('--prices', type=Path, help='Sourced, dated USD price book; omit to leave cost unavailable')
    command.add_argument('--options', type=Path, help='JSON of supported provider options applied identically to all models')
    command.add_argument('--endpoint', default='https://api.openai.com/v1/chat/completions')
    command.add_argument('--key-env', default='OPENAI_API_KEY')
    command.add_argument('--timeout', type=int, default=90)
    command.add_argument('--max-output-tokens', type=int, default=512)
    command.add_argument('--referee-output-tokens', type=int, default=1024)
    command.add_argument('--token-parameter', choices=['max_completion_tokens','max_tokens'], default='max_completion_tokens')
    command = commands.add_parser('plot-evaluation', help='Generate four accuracy/runtime and four accuracy/cost panels')
    command.add_argument('comparison', type=Path)
    command.add_argument('--output', required=True, type=Path)
    command.add_argument('--cost-scope', choices=['evaluation','pipeline'], default='evaluation')
    command = commands.add_parser('convert-json')
    command.add_argument('input', type=Path)
    command.add_argument('--output', required=True, type=Path)
    command.add_argument('--source')
    command.add_argument('--retrieved-at')
    for name in ('inspect', 'candidates'):
        command = commands.add_parser(name)
        command.add_argument('bundle', type=Path)
    command = commands.add_parser('extract', help='Extract unreviewed reviewer-only states and recorded actions')
    command.add_argument('bundle', type=Path)
    command.add_argument('--output', required=True, type=Path)
    command = commands.add_parser('score-kpis', help='Score trusted three-KPI suite/run artifacts')
    command.add_argument('suite', type=Path)
    command.add_argument('run', type=Path)
    command.add_argument('--weights', nargs=3, type=float, metavar=('STATE', 'HUMAN', 'RULES'))
    command = commands.add_parser('card-metadata', help='Cache current YGOPRODeck names/text by explicit replay passcodes')
    command.add_argument('bundle', type=Path)
    command.add_argument('--response', type=Path, help='Use a saved API response offline instead of fetching')
    command.add_argument('--retrieved-at', required=True)
    command.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'evaluate':
            from .evaluation import evaluate
            from .transports import OpenAICompatible
            transport = OpenAICompatible(args.endpoint, key_env=args.key_env, timeout_seconds=args.timeout,
                max_output_tokens=args.max_output_tokens, referee_output_tokens=args.referee_output_tokens,
                token_parameter=args.token_parameter)
            reports = evaluate(args.dataset,args.output,args.models,transport,referee_model=args.referee_model,
                prices=json.loads(read_text(args.prices)) if args.prices else None,
                options=json.loads(read_text(args.options)) if args.options else None,timeout_seconds=args.timeout)
            output = {'comparison':str(args.output/'comparison.json'),
                      'models':[{'model':r['model'],'final_score_percent':r['score']['final_score_percent']} for r in reports]}
        elif args.command == 'plot-evaluation':
            from .evaluation_plots import plot_comparison
            output = plot_comparison(json.loads(read_text(args.comparison)),args.output,cost_scope=args.cost_scope)
        elif args.command == 'extract':
            from .extraction import extract_observations, write_extraction
            output = write_extraction(extract_observations(load_bundle(args.bundle)), args.output)
        elif args.command == 'score-kpis':
            from .kpis import KPI_NAMES, score_kpis
            weights = dict(zip(KPI_NAMES, args.weights)) if args.weights is not None else None
            output = score_kpis(json.loads(read_text(args.suite)), json.loads(read_text(args.run)), weights)
        elif args.command == 'card-metadata':
            from .card_metadata import build_metadata, fetch_response
            if args.output.exists():
                raise ValueError('Card metadata already exists; select a new path')
            replay = load_bundle(args.bundle)
            response = read_bytes(args.response) if args.response else fetch_response(replay)
            if len(response) > 64 * 1024 * 1024:
                raise ValueError('Card API response exceeds 64 MiB')
            report = build_metadata(replay, response, args.retrieved_at)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            output = {key: report[key] for key in ('source_replay', 'requested_distinct_passcodes',
                'matched_distinct_passcodes', 'missing_passcodes', 'historical_rules_verified')}
        else:
            if args.command == 'convert-json':
                from .native_json import convert_json, parse_export
                replay = convert_json(parse_export(read_text(args.input)), args.source, args.retrieved_at)
                write_bundle(replay, args.output)
            else:
                replay = load_bundle(args.bundle)
            output = decision_candidates(replay) if args.command == 'candidates' else summary(replay)
        print(json.dumps(output, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
