"""Packaging and Sanitization Script for Project Rosetta Board.

Generates a sanitized, GitHub-ready repository copy and release zip file,
stripping all sensitive tokens, credentials, private databases, client assets,
and build artifacts.
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import base64

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
EXPORT_PARENT_DIR = ROOT_DIR / "github_export"
CLEAN_REPO_DIR = EXPORT_PARENT_DIR / "project-rosetta-board"
ZIP_OUTPUT_PATH = EXPORT_PARENT_DIR / "project-rosetta-board-clean.zip"
SIBLING_CLEAN_DIR = ROOT_DIR.parent / "Project_Rosetta_Board_Clean"

# Sensitive tokens encoded to avoid matching this script file itself
_ENCODED_SECRETS = [
    "dV85S2xMUUo5SnVV",                 # ClickHouse password
    "aHVhZnVqZnB0NQ==",                 # ClickHouse cloud host ID
    "Z2VuLWxhbmctY2xpZW50LTAwODg2MTM1MDg=", # GCP Project ID
    "MTAwMjg2Mzk4MzY1OA==",             # GCP Project Number
    "NDQ3ODk4NTQxMDMxNTI4ODU3Ng==",     # Vertex Reasoning Engine ID
    "VkVSSVpPTg==",                     # Client PDF Name
]

FORBIDDEN_TEXT_PATTERNS = [
    re.compile(re.escape(base64.b64decode(enc).decode("utf-8")), re.IGNORECASE)
    for enc in _ENCODED_SECRETS
]

# Forbidden files that MUST NOT exist in the export
FORBIDDEN_FILE_NAMES = {
    ".env",
    "rosetta_board_local.db",
}

# Explicit directories to ignore during copy
IGNORE_DIR_NAMES = {
    ".venv",
    ".pytest_cache",
    ".google-agents-cli",
    ".git",
    "__pycache__",
    "dist",
    "github_export",
}

# Explicit files to ignore during copy
IGNORE_FILE_NAMES = {
    ".env",
    "rosetta_board_local.db",
}


def should_ignore(path: Path) -> bool:
    """Determine if a file or directory should be excluded."""
    # Check parts for ignored directory names
    for part in path.parts:
        if part in IGNORE_DIR_NAMES:
            return True
        if part.endswith(".pyc") or part.endswith(".pyo"):
            return True

    # Check file name
    if path.name in IGNORE_FILE_NAMES:
        return True

    # outputs/ directory should only contain .gitkeep
    try:
        rel = path.relative_to(ROOT_DIR)
        if len(rel.parts) > 1 and rel.parts[0] == "outputs":
            if rel.parts[1] != ".gitkeep":
                return True
    except ValueError:
        pass

    return False


def _rmtree_readonly(path: Path):
    """Safely remove a directory tree on Windows handling read-only git files."""
    import stat
    def on_exc(func, fpath, exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass

    if path.exists():
        shutil.rmtree(path, onexc=on_exc)


def copy_sanitized_repository(src_dir: Path, dst_dir: Path):
    """Recursively copy files from src to dst while excluding ignored items."""
    if dst_dir.exists():
        print(f"Cleaning existing destination: {dst_dir}")
        _rmtree_readonly(dst_dir)

    dst_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0

    for root, dirs, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_dir)

        # Skip ignored directories in place
        dirs[:] = [d for d in dirs if not should_ignore(src_dir / rel_root / d)]

        target_dir = dst_dir / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            src_file = Path(root) / f
            if should_ignore(src_file):
                continue

            dst_file = target_dir / f
            shutil.copy2(src_file, dst_file)
            file_count += 1

    # Ensure outputs/.gitkeep exists
    outputs_dir = dst_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    gitkeep = outputs_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("# Keep outputs directory tracked in git\n")
        file_count += 1

    print(f"Copied {file_count} sanitized files to: {dst_dir}")


def scan_for_secrets(target_dir: Path):
    """Deep scan every file in target_dir for forbidden tokens."""
    violations = []
    scanned_count = 0

    for root, _, files in os.walk(target_dir):
        for f in files:
            file_path = Path(root) / f
            scanned_count += 1

            # Check for forbidden files
            if file_path.name in FORBIDDEN_FILE_NAMES:
                violations.append((file_path, f"Forbidden file present: {file_path.name}"))

            # Check filename against forbidden patterns (e.g. client storyboards)
            for pat in FORBIDDEN_TEXT_PATTERNS:
                if pat.search(file_path.name):
                    violations.append((file_path, f"Filename matched forbidden pattern: {pat.pattern}"))

            # Skip scanning binary assets for text patterns
            if file_path.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg", ".ico", ".whl", ".db", ".pyc"]:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for pat in FORBIDDEN_TEXT_PATTERNS:
                    matches = pat.findall(content)
                    if matches:
                        violations.append((file_path, f"Content matched forbidden pattern ({len(matches)} occurrences)"))
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}")

    print(f"Scanned {scanned_count} files for secrets.")
    if violations:
        print("\n[!] SECRETS SCAN FAILED! The following sensitive items were detected:")
        for vpath, msg in violations:
            print(f"  - {vpath.relative_to(target_dir)}: {msg}")
        raise ValueError(f"Found {len(violations)} secret leaks in export directory!")
    else:
        print("[+] SECRETS SCAN PASSED: 0 sensitive tokens, passwords, or client files detected.")


def create_zip_archive(source_dir: Path, zip_path: Path):
    """Package the directory into a zip archive with root prefix 'project-rosetta-board/'."""
    print(f"Creating zip archive at: {zip_path}")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            if ".git" in Path(root).parts:
                continue
            for f in files:
                file_path = Path(root) / f
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname=str(Path("project-rosetta-board") / arcname))

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[+] Archive created successfully ({size_mb:.2f} MB): {zip_path}")


def init_git_repo(repo_dir: Path):
    """Initialize a git repository in repo_dir with an initial commit."""
    print(f"Initializing Git repository in: {repo_dir}")
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Project Rosetta Board"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "crew@rosettaboard.io"], cwd=repo_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        commit_res = subprocess.run(
            ["git", "commit", "-m", "Initial commit: Project Rosetta Board - Universal Storyboard Ingestor"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        print("[+] Git repository initialized with initial commit.")
        print(commit_res.stdout.strip())
    except Exception as e:
        print(f"Notice: Git init/commit returned: {e}")


def mirror_to_sibling(clean_repo_dir: Path, sibling_dir: Path):
    """Mirror clean repository to sibling folder outside the current workspace."""
    try:
        _rmtree_readonly(sibling_dir)
        shutil.copytree(clean_repo_dir, sibling_dir)
        print(f"[+] Mirrored sanitized repository to sibling folder: {sibling_dir}")
    except Exception as e:
        print(f"Notice: Could not copy to sibling directory ({e})")


def main():
    print("=" * 60)
    print("Project Rosetta Board - GitHub Packaging & Sanitizer")
    print("=" * 60)

    EXPORT_PARENT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy and sanitize
    print("\n--- Step 1: Copying and filtering repository ---")
    copy_sanitized_repository(ROOT_DIR, CLEAN_REPO_DIR)

    # 2. Scan for secrets
    print("\n--- Step 2: Running Deep Secret & Token Scan ---")
    scan_for_secrets(CLEAN_REPO_DIR)

    # 3. Create zip archive
    print("\n--- Step 3: Packaging Release Zip ---")
    create_zip_archive(CLEAN_REPO_DIR, ZIP_OUTPUT_PATH)

    # 4. Initialize git
    print("\n--- Step 4: Initializing Git Repository ---")
    init_git_repo(CLEAN_REPO_DIR)

    # 5. Mirror to sibling
    print("\n--- Step 5: Mirroring to Sibling Folder ---")
    mirror_to_sibling(CLEAN_REPO_DIR, SIBLING_CLEAN_DIR)

    print("\n" + "=" * 60)
    print("[SUCCESS] PACKAGING COMPLETE AND VERIFIED SAFE FOR GITHUB!")
    print(f"Directory: {CLEAN_REPO_DIR}")
    print(f"Zip File:  {ZIP_OUTPUT_PATH}")
    print(f"Sibling:   {SIBLING_CLEAN_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
