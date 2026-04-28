from pathlib import Path
import subprocess
import sys


def test_validation_evidence_binding_checker_passes_for_repo() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / 'scripts' / 'check_validation_evidence_binding.py'
    result = subprocess.run([sys.executable, str(script)], cwd=repo_root, check=False, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
