"""Storage and integrity checks for Duelingbook observation bundles."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

SCHEMA_VERSION = '1.0'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def replay_id(value):
    if not isinstance(value,str):
        raise ValueError('Replay ID must be text')
    if '://' in value:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.hostname not in {'duelingbook.com','www.duelingbook.com'}
                or parsed.path not in {'/replay','/replay.php','/view-replay'}):
            raise ValueError('Expected an HTTPS DuelingBook replay URL')
        ids = parse_qs(parsed.query).get('id',[])
        if len(ids) != 1:
            raise ValueError('Expected one replay ID')
        value = ids[0]
    if not re.fullmatch(r'[1-9][0-9]*(?:-[1-9][0-9]*)?',value):
        raise ValueError('Expected numeric duel ID or user-duel ID')
    return value


def restore_source(replay):
    validate(replay)
    from copy import deepcopy
    return deepcopy(replay['source_metadata']['data'])


def validate(replay):
    if replay.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported replay schema version')
    if replay['source']['adapter'] != 'duelingbook-json-v1':
        raise ValueError('Unsupported replay adapter; import native Duelingbook JSON')
    from .native_json import validate_json
    return validate_json(replay)


def write_bundle(replay, directory):
    validate(replay)
    directory = Path(directory)
    if directory.exists():
        raise ValueError('Output directory already exists; select a new version/path')
    directory.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    import shutil
    temporary = Path(tempfile.mkdtemp(prefix='.replay-',dir=directory.parent))
    try:
        (temporary/'events').mkdir()
        references=[]
        for event in replay['events']:
            relative=f"events/{event['sequence']:06d}.json"
            content=canonical(event)+b'\n'
            (temporary/relative).write_bytes(content)
            references.append({'sequence':event['sequence'],'path':relative,'sha256':hashlib.sha256(content).hexdigest()})
        manifest={key:value for key,value in replay.items() if key!='events'}
        manifest['events']=references
        manifest['event_count']=len(references)
        (temporary/'replay.json').write_bytes(canonical(manifest)+b'\n')
        temporary.rename(directory)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def load_bundle(directory):
    directory=Path(directory).resolve()
    manifest=json.loads((directory/'replay.json').read_text(encoding='utf-8'))
    references=manifest.pop('events')
    if manifest.pop('event_count') != len(references):
        raise ValueError('Event count mismatch')
    events=[]
    for index,reference in enumerate(references):
        expected=f'events/{index+1:06d}.json'
        if reference['sequence']!=index+1 or reference['path']!=expected:
            raise ValueError('Invalid event path/order')
        path=(directory/expected).resolve()
        if not path.is_relative_to(directory):
            raise ValueError('Event path escapes bundle')
        content=path.read_bytes()
        if hashlib.sha256(content).hexdigest()!=reference['sha256']:
            raise ValueError('Event file digest mismatch')
        events.append(json.loads(content))
    manifest['events']=events
    return validate(manifest)

