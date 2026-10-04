"""Check repository Markdown local targets and duplicate ADR numbers (read-only)."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.MULTILINE)

def check(root=ROOT):
    errors = []
    paths = [root / "README.md", root / "AGENTS.md", *sorted((root / "docs").rglob("*.md"))]
    for path in paths:
        if not path.exists():
            errors.append(f"Missing documentation: {path.relative_to(root)}")
            continue
        content = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in [*LINK.finditer(content), *REFERENCE.finditer(content)]:
            target = match.group(1).strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(root)}: missing target {target}")
    seen = {}
    for path in sorted((root / "docs" / "adr").glob("*.md")):
        match = re.match(r"^(\d{4})-", path.name)
        if match:
            number = match.group(1)
            if number in seen:
                errors.append(f"Duplicate ADR {number}: {seen[number]} and {path.name}")
            seen[number] = path.name
    return errors

if __name__ == "__main__":
    errors = check()
    for error in errors:
        print(error)
    print(f"Documentation check: {len(errors)} error(s).")
    sys.exit(bool(errors))
