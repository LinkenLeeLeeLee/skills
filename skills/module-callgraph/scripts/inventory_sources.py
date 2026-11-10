#!/usr/bin/env python3
"""List source candidates and their owning Gradle modules; infer no call edges."""

import argparse
import json
import re
import subprocess
from pathlib import Path


def git_value(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def ownership(path, root):
    for directory in path.parents:
        if directory == root:
            break
        if (directory / "build.gradle").is_file() or (directory / "build.gradle.kts").is_file():
            parent = directory.parent.name
            leaf = directory.name
            prefix = parent + "-"
            module = parent if leaf.startswith(prefix) else leaf
            submodule = leaf[len(prefix):] if leaf.startswith(prefix) else None
            return {
                "module": module,
                "submodule": submodule,
                "label": module + "." + submodule if submodule else module,
                "gradle_directory": directory.relative_to(root).as_posix(),
            }
    return {"module": None, "submodule": None, "label": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Repository or worktree root")
    parser.add_argument("pattern", help="Ripgrep regular expression for candidate sources")
    parser.add_argument("--limit", type=int, default=120, help="Maximum candidate files")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error("Repository root does not exist")
    result = subprocess.run(
        ["rg", "-l", "--glob", "**/src/main/**/*.groovy", "--glob",
         "**/src/main/**/*.java", "--glob", "!**/build/**", "--glob", "!**/.gradle/**",
         "-e", args.pattern, "."],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode not in (0, 1):
        parser.exit(2, result.stderr)
    candidates = sorted(result.stdout.splitlines())
    files = []
    for name in candidates[:args.limit]:
        path = (root / name).resolve()
        source = path.read_text(encoding="utf-8")
        package = re.search(r"(?m)^\s*package\s+([\w.]+)", source)
        declarations = []
        for number, line in enumerate(source.splitlines(), 1):
            match = re.match(
                r"^(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed)\s+)*"
                r"(?:class|interface|enum|trait|record)\s+(\w+)", line
            )
            if match:
                declarations.append({"name": match.group(1), "line": number})
        files.append({
            "path": str(path), "relative_path": path.relative_to(root).as_posix(),
            "package": package.group(1) if package else None,
            "declarations": declarations, **ownership(path, root),
        })
    print(json.dumps({
        "root": str(root), "branch": git_value(root, "branch", "--show-current"),
        "commit": git_value(root, "rev-parse", "HEAD"),
        "dirty": bool(git_value(root, "status", "--porcelain")),
        "pattern": args.pattern, "candidate_count": len(candidates),
        "truncated": len(candidates) > args.limit,
        "note": "Text matches are discovery candidates, not proven call edges.", "files": files,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
