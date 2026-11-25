import asyncio
from pathlib import Path
import json
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def to_json(dict: list[dict], name: str):
    print(f"Parsed {len(dict)} {name} entries")
    out_path = Path(f"data/{name}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dict, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Created {out_path}")