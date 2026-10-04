import json
from pathlib import Path
import tempfile

def save(path, data):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        temp = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)

