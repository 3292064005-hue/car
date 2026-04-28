from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from embedded_source_sync import validate_embedded_mirrors


def test_embedded_canonical_source_layout_exists_and_matches_mirrors() -> None:
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'src').is_dir()
    assert (ROOT / 'stm32_code' / 'stm32_f103_chassis' / 'include').is_dir()
    result = validate_embedded_mirrors()
    assert result['status'] == 'ok'
