"""Saved isolation requirements, independent of human card management."""
POLICIES = ('cooperative', 'enforced')


def saved_policy(document):
    # Missing means a legacy save: never silently weaken its requirements.
    policy = document.get('player_isolation', 'enforced')
    if policy not in POLICIES:
        raise ValueError('Choose cooperative or enforced player_isolation')
    return policy


def startup_policy(config):
    if 'player_isolation' in config:
        return saved_policy(config)
    return 'enforced' if config.get('mode') in ('open', 'blind') else 'cooperative'
