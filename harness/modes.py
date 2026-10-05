"""Human card management; legacy open additionally shared human information."""
MODES = ("managed", "self", "agent-vs-agent", "open", "blind")


def self_managed(mode):
    return mode in ("self", "blind")


def managed_cards(mode):
    return mode in ("managed", "open", "agent-vs-agent")


def shared_human_information(mode):
    # Preserve legacy saved games. New managed games use private opponent views.
    return mode == "open"
