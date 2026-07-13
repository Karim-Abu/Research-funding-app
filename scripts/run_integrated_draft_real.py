"""R5.9-REAL — CLI-Wrapper für den manuellen Real-Provider Integrated Draft Run.

Frische Temp-SQLite-DB pro Lauf (nie die Dev-DB, nie eine Datei im Repo),
``os.chdir(backend/)`` damit pydantics CWD-relatives ``env_file=".env"`` die Keys aus
``backend/.env`` lädt. Delegiert die CLI/Guards an ``integrated_draft_real.main``.

Manual Mode: ``RUN_REAL_PROVIDER_SMOKE=true AI_EVAL_MODE=real python
scripts/run_integrated_draft_real.py --provider <openai|anthropic>`` (CI ungesetzt).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_SMOKE_DB = Path(tempfile.gettempdir()) / "integrated_draft_real.db"
if _SMOKE_DB.exists():
    _SMOKE_DB.unlink()  # frischer Zustand pro Lauf

os.environ["DATABASE_URL"] = f"sqlite:///{_SMOKE_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
os.chdir(_BACKEND)  # env_file=".env" ist CWD-relativ → backend/.env (Keys)
sys.path.insert(0, str(_BACKEND))

from app.evaluation.integrated_draft_real import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
