"""Human and model clients share an information-limited decision interface."""
from copy import deepcopy
from typing import Protocol


class PlayerAdapter(Protocol):
    def choose(self, context: dict) -> dict: ...


class CallbackPlayer:
    def __init__(self, callback):
        self.callback = callback

    def choose(self, context):
        return self.callback(deepcopy(context))
