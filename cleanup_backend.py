from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CANONICAL_DB = DATA_DIR / "lazarus_safe.db"
BACKUP_DIR = ROOT / "_cleanup_backup"

BACKUP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

PY_EXTENSIONS = {".py"}

# pattern-uri pe care le reparăm
REPLACEMENTS = [
    (
        re.compile(r'BASE_DIR\s*/\s*"lazarus_safe_v2\.db"'),
        'BASE_DIR / "data" / "lazarus_safe.db"',
    ),
    (
        re.compile(r'BASE_DIR\s*/\s*"lazarus_safe\.db"'),
        'BASE_DIR / "data" / "lazarus_safe.db"',
    ),
    (
        re.compile(r'["\']lazarus_safe_v2\.db["\']'),
        '"data/lazarus_safe.db"',
    ),
    (
        re.compile(r'["\']lazarus_safe\.db["\']'),
        '"data/lazarus_safe.db"',
    ),
]

# fișiere pe care le ignorăm
IGNORE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "_cleanup_backup",
}

changed_files = []
moved_files = []


def should_skip(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def backup_file(path: Path):
    rel = path.relative_to(ROOT)
    dst = BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)


def fix_python_files():
    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        if should_skip(path):
            continue
        if path.suffix not in PY_EXTENSIONS:
            continue

        try:
            original = path.read_text(encoding="utf-8")
        except Exception:
            continue

        updated = original

        for pattern, replacement in REPLACEMENTS:
            updated = pattern.sub(replacement, updated)

        # curățare cazuri duble de tip data/data/lazarus_safe.db
        updated = updated.replace('data/data/lazarus_safe.db', 'data/lazarus_safe.db')

        if updated != original:
            backup_file(path)
            path.write_text(updated, encoding="utf-8")
            changed_files.append(str(path.relative_to(ROOT)))


def move_or_cleanup_databases():
    root_db = ROOT / "lazarus_safe.db"
    root_v2_db = ROOT / "lazarus_safe_v2.db"
    data_db = ROOT / "data" / "lazarus_safe.db"

    # dacă există baza în root și nu există în data/, o mutăm acolo
    if root_db.exists() and not data_db.exists():
        backup_file(root_db)
        shutil.move(str(root_db), str(data_db))
        moved_files.append(f"moved {root_db.name} -> data/{data_db.name}")

    # dacă există și în root și în data, păstrăm varianta din data și mutăm pe cea din root în backup
    elif root_db.exists() and data_db.exists():
        backup_file(root_db)
        root_db.unlink()
        moved_files.append(f"removed duplicate root db: {root_db.name}")

    # v2 trebuie scos complet din lucru curent
    if root_v2_db.exists():
        backup_file(root_v2_db)
        root_v2_db.unlink()
        moved_files.append(f"removed legacy db: {root_v2_db.name}")


def main():
    fix_python_files()
    move_or_cleanup_databases()

    print("\n=== CLEANUP BACKEND REPORT ===")
    print(f"Canonical DB: {CANONICAL_DB}")

    if changed_files:
        print("\nModified Python files:")
        for f in changed_files:
            print(f" - {f}")
    else:
        print("\nNo Python files needed changes.")

    if moved_files:
        print("\nDatabase cleanup:")
        for f in moved_files:
            print(f" - {f}")
    else:
        print("\nNo database files needed moving/removal.")

    print(f"\nBackups saved in: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
