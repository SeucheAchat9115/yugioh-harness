"""Native replay work items for reviewers, never scored cases or player packets."""


def decision_candidates(replay):
    kinds = {'summon', 'set', 'activation_observation', 'attack', 'phase', 'turn'}
    return [
        {'id': f"{replay['id']}-before-{event['sequence']:06d}",
         'source': {'replay': replay['id'], 'before_sequence': event['sequence'],
                    'source_index': event['source_index']},
         'game': event['game'], 'actor': event['actor'],
         'observation_kind': event['kind'], 'review': {'status': 'unreviewed'},
         'required_review': ['state', 'information_visibility', 'rules', 'decision_boundary', 'grading']}
        for event in replay['events'] if event['kind'] in kinds and event['actor'] is not None
    ]
