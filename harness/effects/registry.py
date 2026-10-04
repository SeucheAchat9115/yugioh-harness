"""Explicit effect support. Unknown interactions require a moderator ruling."""
from copy import deepcopy


class UnsupportedEffect(ValueError):
    pass


class EffectRegistry:
    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        if name in self._handlers:
            raise ValueError('Effect handler already registered')
        self._handlers[name] = handler

    def prepare(self, name, state, request):
        if name not in self._handlers:
            raise UnsupportedEffect(f'No handler for {name}; moderator ruling required')
        return self._handlers[name](deepcopy(state), deepcopy(request))

    def capabilities(self):
        return sorted(self._handlers)
