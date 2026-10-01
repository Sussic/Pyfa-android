"""Shared evidence location; hosted defaults remain compatible."""
import os
from pathlib import Path


def evidence_dir():
    path = Path(os.environ.get('PYFA_EVIDENCE_DIR', Path(__file__).resolve().parents[1] / 'build/evidence')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
