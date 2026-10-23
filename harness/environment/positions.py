"""Initialize fixed positions through the same journals/checkpoints as live play.

Callers must review source positions and pin their assets before invoking this
helper. Structural validation does not certify a ruling or reconstruct a replay.
"""
from copy import deepcopy
from pathlib import Path
import re

from harness.engine.actions import initialize, publish_verified, validate_state
from harness.isolation import saved_policy
from harness.storage.atomic import save


def create_position(root, *, position_id, configuration, state, rules_text):
    """Create a fresh resumable position, without shuffling or exposing grading data."""
    if not isinstance(position_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', position_id):
        raise ValueError('Position ID must be a lowercase slug')
    state, configuration = deepcopy(state), deepcopy(configuration)
    validate_state(state)
    if (configuration.get('id') != state['game_id'] or configuration.get('mode') != state['mode']
            or saved_policy(configuration) != saved_policy(state) or state.get('revision') != 0):
        raise ValueError('New position configuration and revision must match its state')
    if not isinstance(rules_text, str) or not rules_text.strip():
        raise ValueError('Pinned rules text is required')
    if not configuration.get('format') or not configuration.get('rules_version') or not configuration.get('banlist'):
        raise ValueError('Pin the format, rules version and banlist')
    root = Path(root).resolve()
    private = root / 'private' / position_id
    game = root / 'archive' / 'games' / 'reviewed-checkpoint' / position_id
    if private.exists() or game.exists():
        raise ValueError('Position already exists; resume rather than resetting it')
    private.mkdir(parents=True, mode=0o700)
    game.mkdir(parents=True)
    save(game / 'game.json', configuration)
    (game / 'rules.md').write_text(rules_text, encoding='utf-8')
    journal = initialize(state)
    save(private / 'journal.json', journal)
    publish_verified(journal, state, private / 'state.json', game)
    save(private / 'session.json', {'game_dir': str(game)})
    return private / 'state.json', game
