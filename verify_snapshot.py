"""Check the frozen mod assets against SHA256SUMS; no external dependencies."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent
errors = []
for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    expected, relative = line.split("  ", 1)
    path = root / relative
    if not path.is_file():
        errors.append(f"missing: {relative}")
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual.lower() != expected.lower():
        errors.append(f"mismatch: {relative}")
    else:
        print(f"OK {relative}")
if errors:
    raise SystemExit("\n".join(errors))
print("Frozen mod assets match SHA256SUMS.")

