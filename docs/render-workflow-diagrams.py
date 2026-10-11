#!/usr/bin/env python3
"""Render the guide's Mermaid sources with an externally installed Mermaid CLI."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mermaid-cli', default='mmdc')
    parser.add_argument('--puppeteer-config', type=Path)
    args = parser.parse_args()
    docs = Path(__file__).resolve().parent
    source = (docs / 'workflows-and-context.md').read_text(encoding='utf-8')
    diagrams = re.findall(
        r'!\[[^\]]*\]\(diagrams/([a-z-]+)\.svg\)\s*'
        r'<details>\s*<summary>Editable Mermaid source</summary>\s*'
        r'```mermaid\n(.*?)\n```', source, re.S)
    if len(diagrams) != 6:
        raise ValueError('Expected six images with matching Mermaid source blocks')
    (docs / 'diagrams').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        for name, diagram in diagrams:
            input_path = Path(directory) / f'{name}.mmd'
            input_path.write_text(diagram + '\n', encoding='utf-8')
            command = [args.mermaid_cli, '-i', str(input_path), '-o',
                       str(docs / 'diagrams' / f'{name}.svg'), '-b', 'white']
            if args.puppeteer_config:
                command.extend(['-p', str(args.puppeteer_config.resolve())])
            subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
