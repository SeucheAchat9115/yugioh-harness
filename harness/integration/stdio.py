"""Consistent Unicode input/output for JSON and conversational CLI transports."""
import sys


def configure_utf8():
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
