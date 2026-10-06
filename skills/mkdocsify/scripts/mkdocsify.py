#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mkdocsify - turn a folder of Markdown files into a buildable MkDocs project.

One folder in, one MkDocs project out:

    <folder>/            <folder>/                 (or --out <dir>)
    *.md          -->    docs/*.md
                         docs/static/{logo.svg,style.css}
                         mkdocs.yml          (shadcn theme, fixed)
                         requirements.txt    (pinned deps)
                         .gitignore
                         .venv/              (Python virtualenv)
                         site/               (mkdocs build output)

The theme is fixed to ``shadcn``. There is no configuration surface for
switching themes, by design: this skill exists to make one specific,
already-agreed stack reproducible.

Usage:
    python mkdocsify.py SOURCE [--out DIR] [options]

Run ``python mkdocsify.py --help`` for the full option list.
"""

from __future__ import print_function

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

try:
    from pathlib import Path
except ImportError:  # pragma: no cover - Python 2 fallback guard
    sys.exit("mkdocsify.py requires Python 3.6+ (pathlib)")

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
ASSETS = SKILL_ROOT / "assets"

# Markdown filenames in this vault are frequently bilingual (e.g.
# "01-日常生活 A Day in the Life.md"). Force UTF-8 output so Chinese page
# titles in the log do not turn into mojibake on a non-UTF-8 Windows console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - old interpreters
        pass

VENV_DIRNAME = ".venv"
BUILD_DIRNAME = "site"
DOCS_DIRNAME = "docs"

# Directories that are never treated as source Markdown.
IGNORED_DIRS = {
    DOCS_DIRNAME,
    BUILD_DIRNAME,
    VENV_DIRNAME,
    ".git",
    ".obsidian",
    ".trash",
    "__pycache__",
}

# markdown_extensions that ship with mkdocs/pymdownx and therefore need no
# extra install. Only used to decide whether to *recommend* an extension.
BUILTIN_EXTENSIONS = {"meta", "toc", "extra", "admonition", "attr_list", "codehilite"}

WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)(#[^\[\]|]*)?(\|[^\[\]]*)?\]\]")
LOCAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)

PLUGIN_TO_IMPORT = {
    "search": None,  # built into mkdocs
    "macros": "mkdocs_macros",
    "shadcn.extensions.iconify": None,  # provided by mkdocs-shadcn
}


class Fail(Exception):
    """A user-facing failure with an actionable message."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def info(msg):
    print(msg, flush=True)


def warn(msg):
    print("  ! %s" % msg, flush=True)


def step(msg):
    print("\n[%s]" % msg, flush=True)


def ok(msg):
    print("  + %s" % msg, flush=True)


def run(cmd, cwd, check=True, capture=False):
    """Run a command, streaming output unless capture=True."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        universal_newlines=True,
    )
    if not capture:
        proc.wait()
        if check and proc.returncode != 0:
            raise Fail(
                "command failed (%s): %s" % (proc.returncode, " ".join(map(str, cmd)))
            )
        return proc.returncode, ""
    out, _ = proc.communicate()
    if check and proc.returncode != 0:
        raise Fail(
            "command failed (%s): %s\n%s"
            % (proc.returncode, " ".join(map(str, cmd)), out)
        )
    return proc.returncode, out


def read_text(path):
    with open(str(path), "r", encoding="utf-8-sig") as fh:
        return fh.read()


def write_text(path, text):
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def normalize_key(name):
    """Normalise a page name so it can be matched against a wikilink target.

    ``01-日常生活 A Day in the Life.md``  ->  ``日常生活 a day in the life``
    ``A Day in the Life``                ->  ``a day in the life``
    """
    name = name.strip()
    name = re.sub(r"\.md$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\d+[-_\s]*", "", name)  # leading NN- ordering prefix
    name = name.replace("-", " ").replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name.casefold()


def name_variants(name):
    """Lookup keys for a page name, longest (most specific) first.

    Bilingual filenames such as ``日常生活 A Day in the Life`` are indexed
    under every whitespace-delimited suffix so that a wikilink written as
    ``[[A Day in the Life]]`` still resolves.
    """
    base = normalize_key(name)
    if not base:
        return []
    parts = base.split(" ")
    return [" ".join(parts[i:]) for i in range(len(parts))]


def strip_numeric_prefix(stem):
    """``01-NGSL 主题阅读说明`` -> ``NGSL 主题阅读说明``."""
    return re.sub(r"^\d+[-_\s]*", "", stem).strip()


def numeric_prefix(stem):
    """Leading ordering number as an int, or a large value when absent."""
    m = re.match(r"^(\d+)", stem.strip())
    return int(m.group(1)) if m else 10**6


# Words that mark a page as an introduction / overview rather than a chapter.
INTRO_MARKERS = (
    "说明",
    "导读",
    "介绍",
    "目录",
    "概览",
    "前言",
    "引言",
    "总览",
    "readme",
    "intro",
    "overview",
    "index",
    "guide",
    "about",
)


def is_intro_name(stem):
    """True when a filename marks the page as an introduction or overview."""
    name = strip_numeric_prefix(stem).casefold()
    return any(marker in name for marker in INTRO_MARKERS)


def venv_python(target, windows=None):
    if windows is None:
        windows = os.name == "nt"
    return (
        Path(target)
        / VENV_DIRNAME
        / ("Scripts" if windows else "bin")
        / ("python.exe" if windows else "python")
    )


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------


def looks_like_mkdocs_project(directory):
    return (Path(directory) / "mkdocs.yml").exists() and (
        Path(directory) / DOCS_DIRNAME
    ).is_dir()


def iter_source_markdown(source):
    """Yield (absolute_path, relative_path) for every source Markdown file."""
    source = Path(source)
    for path in sorted(source.rglob("*.md")):
        rel = path.relative_to(source)
        if any(part in IGNORED_DIRS or part == VENV_DIRNAME for part in rel.parts):
            continue
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        yield path, rel


def has_frontmatter(md_files):
    for path in md_files:
        try:
            text = read_text(path)
        except OSError:
            continue
        if FRONTMATTER_RE.match(text):
            return True
    return False


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------


def build_link_corpus(docs_dir):
    """Map every lookup key -> the filenames inside docs/ that claim it."""
    corpus = {}
    for path in sorted(Path(docs_dir).glob("*.md")):
        for key in name_variants(path.name):
            corpus.setdefault(key, [])
            if path.name not in corpus[key]:
                corpus[key].append(path.name)
    return corpus


def resolve_wikilink(target, corpus):
    """Resolve a wikilink target to a filename in docs/.

    Returns (filename, ambiguous). ``None`` means no page claimed the name.
    """
    for key in name_variants(target):
        candidates = corpus.get(key)
        if candidates:
            exact = [c for c in candidates if normalize_key(c) == key]
            if len(exact) == 1:
                return exact[0], False
            return candidates[0], len(candidates) > 1
    return None, False


def convert_wikilinks(docs_dir, corpus, keep_wikilinks=False):
    """Rewrite Obsidian ``[[Target]]`` links into MkDocs relative links.

    Returns (converted, unresolved, skipped, ambiguous) counts.
    """
    converted = unresolved = skipped = ambiguous = 0
    for path in sorted(Path(docs_dir).glob("*.md")):
        text = read_text(path)
        if "[[" not in text:
            continue
        out = []
        pos = 0
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip().split("/")[-1]  # drop any folder prefix
            heading = m.group(2)
            alias = m.group(3)
            out.append(text[pos : m.start()])
            if heading or keep_wikilinks:
                # Cross-file anchors cannot be resolved reliably without
                # rendering the target page first; leave the link untouched.
                out.append(m.group(0))
                skipped += 1
            else:
                filename, is_ambiguous = resolve_wikilink(target, corpus)
                if filename is None:
                    out.append(m.group(0))
                    unresolved += 1
                else:
                    label = alias[1:].strip() if alias else target
                    out.append("[%s](%s)" % (label, urllib.parse.quote(filename)))
                    converted += 1
                    if is_ambiguous:
                        ambiguous += 1
            pos = m.end()
        out.append(text[pos:])
        write_text(path, "".join(out))
    return converted, unresolved, skipped, ambiguous


def copy_referenced_assets(source, docs_dir, md_files):
    """Copy locally-referenced images/assets into docs/, preserving layout."""
    copied = missing = 0
    source = Path(source)
    docs_dir = Path(docs_dir)
    for path in md_files:
        path = Path(path)
        if not path.exists():
            continue  # e.g. the page promoted to index.md
        text = read_text(path)
        for raw in LOCAL_IMAGE_RE.findall(text):
            ref = raw.strip()
            if ref.startswith(("http://", "https://", "data:", "#", "/")):
                continue
            ref_path = urllib.parse.unquote(ref.split("#")[0].split("?")[0])
            src = (source / ref_path).resolve()
            try:
                src.relative_to(source.resolve())
            except ValueError:
                continue  # points outside the source tree; leave it alone
            if not src.exists():
                missing += 1
                continue
            dest = docs_dir / ref_path
            if not dest.parent.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            copied += 1
    return copied, missing


# --------------------------------------------------------------------------
# generated files
# --------------------------------------------------------------------------

MKDOCTS_TEMPLATE = ASSETS / "mkdocs.yml"
GITIGNORE_TEMPLATE = ASSETS / "gitignore.txt"

REQUIREMENTS_HEADER = """# Generated by the mkdocsify skill. Edit freely, then re-run:
#   .venv/Scripts/python.exe -m pip install -r requirements.txt
#
# Requested pins (verbatim from the operator's specification):
#   mkdocs                1.6.11
#   mkdocs-shadcn         0.12.1
#   mkdocs-macros-plugin  1.5.0
#   bottle                0.13.4
#   pymdown-extensions    10.15
#
# NOTE: mkdocs 1.6.11 does not exist on PyPI. The 1.6 series ends at 1.6.1,
# so the pin below is the highest real 1.6.x release. Pass --requirements to
# override with your own file if you need a different version.
"""

DEFAULT_REQUIREMENTS = [
    ("mkdocs", "1.6.1"),
    ("mkdocs-shadcn", "0.12.1"),
    ("mkdocs-macros-plugin", "1.5.0"),
    ("bottle", "0.13.4"),
    ("pymdown-extensions", "10.15"),
]


def write_requirements(target, requirements_text=None):
    path = Path(target) / "requirements.txt"
    if requirements_text is None:
        requirements_text = (
            REQUIREMENTS_HEADER
            + "\n".join("%s==%s" % (name, pin) for name, pin in DEFAULT_REQUIREMENTS)
            + "\n"
        )
    write_text(path, requirements_text)
    return path


def write_mkdocs_yml(target, site_name, site_description, site_url, add_meta_extension):
    template = read_text(MKDOCTS_TEMPLATE)
    text = (
        template.replace("{{site_name}}", site_name)
        .replace("{{site_description}}", site_description)
        .replace("{{site_url}}", site_url)
    )
    if add_meta_extension:
        text = text.replace(
            "markdown_extensions:\n  - abbr",
            "markdown_extensions:\n  - meta\n  - abbr",
            1,
        )
    path = Path(target) / "mkdocs.yml"
    write_text(path, text)
    return path


def write_gitignore(target):
    text = read_text(GITIGNORE_TEMPLATE)
    path = Path(target) / ".gitignore"
    write_text(path, text)
    return path


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


def git_available():
    try:
        subprocess.Popen(
            ["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).wait()
        return True
    except OSError:
        return False


def git(target, *args):
    return run(["git"] + list(args), cwd=target, check=True)


def git_init(target, message):
    """Initialise the repository if needed, then commit everything with `message`."""
    if not git_available():
        warn("git not found on PATH - skipping repository initialisation")
        return False
    if not (Path(target) / ".git").exists():
        try:
            run(["git", "init", "-b", "main"], cwd=target, check=True)
        except Fail:
            git(target, "init")
            code, head = run(
                ["git", "symbolic-ref", "--short", "HEAD"], cwd=target, capture=True
            )
            if code == 0 and head.strip() not in ("main", "master"):
                try:
                    git(target, "branch", "-m", "main")
                except Fail:
                    pass
    git(target, "add", "-A")
    try:
        git(target, "commit", "-m", message)
    except Fail:
        # No git identity, or nothing to commit. Fall back to a repo-local
        # identity so the baseline commit still exists.
        _, name = run(
            ["git", "config", "user.name"], cwd=target, capture=True, check=False
        )
        _, email = run(
            ["git", "config", "user.email"], cwd=target, capture=True, check=False
        )
        if not name.strip() or not email.strip():
            git(target, "config", "user.name", name.strip() or "mkdocsify")
            git(target, "config", "user.email", email.strip() or "mkdocsify@localhost")
            git(target, "add", "-A")
            git(target, "commit", "-m", message)
        else:
            warn("nothing to commit (%s)" % message)
    return True


# --------------------------------------------------------------------------
# python environment
# --------------------------------------------------------------------------


def find_python(explicit=None):
    candidates = []
    if explicit:
        candidates.append(explicit)
    else:
        candidates += [
            sys.executable,
            "python",
            "python3",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python"),
        ]
        if os.name == "nt":
            candidates.append("py")
    seen = set()
    for cand in candidates:
        if not cand:
            continue
        real = cand if os.path.isabs(cand) else shutil.which(cand)
        if not real or real in seen:
            continue
        seen.add(real)
        code, out = run(
            [real, "-c", "import sys;print(sys.version_info[:2])"],
            cwd=".",
            capture=True,
            check=False,
        )
        if code == 0 and out.strip().startswith("(3,"):
            return real
        if cand == "py":
            code, out = run(
                [cand, "-3", "-c", "import sys;print(sys.version_info[:2])"],
                cwd=".",
                capture=True,
                check=False,
            )
            if code == 0 and out.strip().startswith("(3,"):
                return cand
    raise Fail(
        "no Python 3 interpreter found. Install Python 3.8+ or pass --python /path/to/python"
    )


def make_venv(target, python):
    py = venv_python(target)
    if py.exists():
        warn("reusing existing virtual environment %s" % py)
        return py
    run([python, "-m", "venv", VENV_DIRNAME], cwd=target)
    if not py.exists():
        raise Fail("venv created but %s is missing" % py)
    return py


def pip_install(py, target, packages, quiet=True):
    cmd = [str(py), "-m", "pip", "install", "--disable-pip-version-check"]
    if quiet:
        cmd.append("-q")
    cmd += packages
    run(cmd, cwd=target)


def parse_requirements(path):
    """Read requirements.txt into a list of pip requirements."""
    reqs = []
    for line in read_text(path).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            reqs.append(line)
    return reqs


def plugin_requires_install(target_yaml):
    """Extract the plugin names declared in the generated mkdocs.yml."""
    names = []
    lines = read_text(target_yaml).splitlines()
    in_plugins = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("plugins:"):
            in_plugins = True
            continue
        if in_plugins:
            if not stripped:
                continue
            if line.startswith((" ", "\t", "-")) and stripped.startswith("-"):
                names.append(stripped.lstrip("- ").strip())
            else:
                in_plugins = False
    return names


def ensure_plugins(target, py, mkdocs_yml):
    """Install any plugin declared in mkdocs.yml that is missing from the venv."""
    installed = []
    for name in plugin_requires_install(mkdocs_yml):
        module = PLUGIN_TO_IMPORT.get(name, name.replace("-", "_"))
        if module is None:
            continue  # built into mkdocs or provided by the pinned theme
        code, _ = run(
            [str(py), "-c", "import %s" % module], cwd=target, capture=True, check=False
        )
        if code == 0:
            continue
        ok("plugin '%s' is declared in mkdocs.yml but not installed - adding it" % name)
        pip_install(py, target, ["%s" % name], quiet=False)
        installed.append(name)
        req = Path(target) / "requirements.txt"
        if req.exists():
            text = read_text(req)
            if not any(
                ln.strip().lower().startswith(name.lower()) for ln in text.splitlines()
            ):
                write_text(req, text.rstrip("\n") + "\n%s\n" % name)
    return installed


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="mkdocsify.py",
        description="Convert a folder of Markdown files into a buildable MkDocs project (shadcn theme).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("source", nargs="?", help="folder containing the Markdown files")
    p.add_argument(
        "--out",
        metavar="DIR",
        help="write the project here instead of converting in place",
    )
    p.add_argument(
        "--name", metavar="TEXT", help="site_name (default: source folder name)"
    )
    p.add_argument(
        "--description", metavar="TEXT", help="site_description (default: generated)"
    )
    p.add_argument(
        "--site-url",
        metavar="URL",
        default="http://localhost:8081/",
        help="site_url written to mkdocs.yml (default: %(default)s)",
    )
    p.add_argument(
        "--python", metavar="PATH", help="interpreter used to create the venv"
    )
    p.add_argument(
        "--requirements",
        metavar="FILE",
        help="use this requirements file instead of the default pins",
    )
    p.add_argument(
        "--no-venv",
        action="store_true",
        help="skip virtualenv creation and package install",
    )
    p.add_argument("--no-git", action="store_true", help="skip git init / commits")
    p.add_argument(
        "--no-build", action="store_true", help="skip the mkdocs build verification"
    )
    p.add_argument(
        "--build",
        action="store_true",
        help="force a build even if --no-build was given",
    )
    p.add_argument(
        "--keep-wikilinks",
        action="store_true",
        help="do not rewrite Obsidian [[links]]",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="allow re-running over an existing MkDocs project",
    )
    return p


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.source:
        parser.print_help()
        return 2

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise Fail("source folder does not exist: %s" % source)

    in_place = args.out is None
    target = source if in_place else Path(args.out).expanduser().resolve()

    md_rel = list(iter_source_markdown(source))
    already_project = looks_like_mkdocs_project(target)
    if not md_rel and not already_project:
        raise Fail("no Markdown files found under %s" % source)
    if already_project and not args.force:
        raise Fail(
            "%s already looks like a MkDocs project (mkdocs.yml + docs/).\n"
            "      Re-run with --force to refresh static/, mkdocs.yml and .gitignore in place."
            % target
        )
    refresh = already_project and not md_rel
    if refresh:
        md_rel = [
            (p, p.relative_to(target / DOCS_DIRNAME))
            for p in sorted((target / DOCS_DIRNAME).rglob("*.md"))
        ]
        info(
            "refresh mode: no loose Markdown left in the source, updating docs/ in place"
        )

    site_name = args.name or source.name
    site_description = args.description or ("MkDocs site generated from %s" % site_name)

    info("source : %s" % source)
    info("target : %s%s" % (target, "  (in place)" if in_place else ""))
    info("site   : %s  (%d Markdown file(s))" % (site_name, len(md_rel)))

    # --- baseline commit BEFORE touching anything (rollback point) --------
    # Taken on the first run only: if the target already has a .git dir it was
    # converted before (or is someone else's repo), and committing its current
    # state as "original" would be misleading.
    baseline_committed = False
    if not args.no_git and in_place and not (target / ".git").exists():
        step("git: baseline commit of the original folder")
        baseline_msg = (
            "Baseline before mkdocsify refresh"
            if refresh
            else "Original Markdown folder (pre-mkdocsify)"
        )
        baseline_committed = git_init(target, baseline_msg)
        if baseline_committed:
            ok(
                "baseline commit created - 'git reset --hard HEAD~1' restores the earlier state"
            )

    # --- docs/ ------------------------------------------------------------
    step("docs: assembling the MkDocs source tree")
    docs_dir = target / DOCS_DIRNAME
    if docs_dir.exists() and not args.force:
        raise Fail("docs/ already exists in %s (use --force to overwrite)" % target)
    (docs_dir / "static").mkdir(parents=True, exist_ok=True)

    moved = 0
    for abs_path, rel in md_rel:
        dest = docs_dir / rel
        if dest.resolve() == abs_path.resolve():
            continue  # refresh mode: already in place
        if not dest.parent.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
        if in_place:
            shutil.move(str(abs_path), str(dest))
        else:
            shutil.copy2(str(abs_path), str(dest))
        moved += 1
    ok(
        "%d Markdown file(s) %s into docs/" % (moved, "moved" if in_place else "copied")
        if moved
        else "no Markdown file(s) to move (refresh mode)"
    )

    # --- index page -------------------------------------------------------
    # Priority: existing index.md > 00-*.md > a page whose name marks it as an
    # introduction/overview > README.md > a generated file list. The marker
    # step exists because real folders do not always use a 00- prefix:
    # "01-NGSL 主题阅读说明.md" is an introduction numbered 01.
    existing_index = docs_dir / "index.md"
    if existing_index.exists():
        ok("kept existing docs/index.md as the home page")
    else:
        promoted = None
        zero = sorted(docs_dir.glob("00-*.md"))
        if zero:
            promoted = zero[0]
        else:
            marked = [p for p in sorted(docs_dir.glob("*.md")) if is_intro_name(p.stem)]
            if marked:
                promoted = min(marked, key=lambda p: (numeric_prefix(p.stem), p.name))
        if promoted is None:
            readme = docs_dir / "README.md"
            if readme.exists():
                promoted = readme
        if promoted is not None:
            if promoted.resolve() != existing_index.resolve():
                shutil.move(str(promoted), str(existing_index))
            ok("promoted '%s' -> docs/index.md (home page)" % promoted.name)
        else:
            lines = ["# %s" % site_name, ""]
            if site_description:
                lines += [site_description, ""]
            lines += ["## Contents", ""]
            for path in sorted(docs_dir.glob("*.md")):
                title = re.sub(r"^\d+[-_\s]*", "", path.stem).strip() or path.stem
                lines.append("- [%s](%s)" % (title, urllib.parse.quote(path.name)))
            write_text(existing_index, "\n".join(lines) + "\n")
            ok("generated docs/index.md from the file list")

    # --- static assets ----------------------------------------------------
    static_src = ASSETS / "static"
    if static_src.is_dir():
        for asset in sorted(static_src.iterdir()):
            if asset.is_file():
                shutil.copy2(str(asset), str(docs_dir / "static" / asset.name))
        ok(
            "copied %d static asset(s) into docs/static/"
            % len(list((docs_dir / "static").iterdir()))
        )

    # --- referenced images ------------------------------------------------
    copied_assets, missing_assets = copy_referenced_assets(
        source, docs_dir, [docs_dir / rel for _, rel in md_rel]
    )
    if copied_assets:
        ok("copied %d locally-referenced image/asset file(s)" % copied_assets)
    if missing_assets:
        warn(
            "%d referenced image(s) were not found in the source folder"
            % missing_assets
        )

    # --- wikilinks --------------------------------------------------------
    step("links: rewriting Obsidian [[wikilinks]]")
    corpus = build_link_corpus(docs_dir)
    converted, unresolved, skipped, ambiguous = convert_wikilinks(
        docs_dir, corpus, keep_wikilinks=args.keep_wikilinks
    )
    if args.keep_wikilinks:
        ok("left untouched (--keep-wikilinks)")
    else:
        ok(
            "%d wikilink(s) converted, %d unresolved, %d skipped%s"
            % (
                converted,
                unresolved,
                skipped,
                ", %d ambiguous" % ambiguous if ambiguous else "",
            )
        )
    if unresolved:
        warn(
            "%d wikilink(s) point at pages that do not exist - left as [[...]]"
            % unresolved
        )
    for path in sorted(docs_dir.glob("*.md")):
        if "[[" in read_text(path):
            warn("still contains [[wikilinks]]: %s" % path.name)
            break

    # --- config -----------------------------------------------------------
    step("config: writing mkdocs.yml, requirements.txt, .gitignore")
    frontmatter_present = has_frontmatter(sorted(docs_dir.rglob("*.md")))
    mkdocs_yml = write_mkdocs_yml(
        target,
        site_name,
        site_description,
        args.site_url,
        add_meta_extension=frontmatter_present,
    )
    if frontmatter_present:
        ok("frontmatter detected - added the 'meta' markdown extension")
    requirements = None
    if args.requirements:
        src = Path(args.requirements).expanduser().resolve()
        if not src.exists():
            raise Fail("requirements file not found: %s" % src)
        requirements = read_text(src)
    write_requirements(target, requirements)
    write_gitignore(target)
    ok(
        "mkdocs.yml (theme: shadcn), requirements.txt, .gitignore written to project root"
    )

    # --- python environment ----------------------------------------------
    install_failed = False
    if not args.no_venv:
        step("python: creating the virtual environment")
        python_exe = find_python(args.python)
        py = make_venv(target, python_exe)
        ok("venv ready: %s" % py)
        run(
            [str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"],
            cwd=target,
            check=False,
        )
        reqs = parse_requirements(target / "requirements.txt")
        step("python: installing pinned dependencies")
        try:
            pip_install(py, target, reqs, quiet=False)
        except Fail as exc:
            install_failed = True
            print(
                "  x dependency install FAILED\n"
                "      %s\n"
                "      The file conversion itself finished. Common causes, in order:\n"
                "        - no network / a corporate proxy is blocking pypi.org\n"
                "        - one of the pins does not exist (see the note in requirements.txt)\n"
                "      Retry once the network is back:\n"
                "        %s -m pip install -r %s"
                % (
                    " ".join(str(c) for c in [py, "-m", "pip", "install", *reqs]),
                    py,
                    target / "requirements.txt",
                )
            )
        if not install_failed:
            ensure_plugins(target, py, mkdocs_yml)
            code, out = run(
                [str(py), "-c", "import mkdocs, shadcn; print(mkdocs.__version__)"],
                cwd=target,
                capture=True,
            )
            ok("installed (mkdocs %s)" % out.strip())
    else:
        warn("skipped virtualenv (--no-venv)")

    # --- build ------------------------------------------------------------
    do_build = args.build or not (args.no_build or args.no_venv or install_failed)
    build_failed = False
    if do_build:
        step("build: mkdocs build")
        py = venv_python(target)
        if not py.exists():
            warn("no venv present - skipping build")
        else:
            code, out = run(
                [str(py), "-m", "mkdocs", "build", "--clean"], cwd=target, check=False
            )
            tail = "\n".join(out.strip().splitlines()[-15:])
            if code != 0:
                build_failed = True
                print("  x mkdocs build FAILED\n%s" % tail)
            else:
                ok("site built into site/")
    elif args.no_build:
        warn("skipped build (--no-build)")

    # --- git --------------------------------------------------------------
    committed = False
    if not args.no_git:
        step("git: committing the converted project")
        committed = git_init(
            target, "mkdocsify: convert to a MkDocs project (shadcn theme)"
        )
        if committed:
            ok("project committed")

    # --- summary ----------------------------------------------------------
    step("done")
    venv_py = venv_python(target)
    if venv_py.exists():
        serve_cmd = '"%s" -m mkdocs serve' % venv_py
    else:
        serve_cmd = "mkdocs serve  (activate a virtualenv with the pinned deps first)"
    print(
        "\n".join(
            [
                "  project   : %s" % target,
                "  home page : docs/index.md",
                "  theme     : shadcn (fixed)",
                "  serve     : %s" % serve_cmd,
                "",
                "  rollback  : %s"
                % (
                    "git reset --hard HEAD~1"
                    if committed and baseline_committed
                    else "n/a (no baseline commit taken)"
                ),
            ]
        )
    )
    if install_failed:
        return 3
    return 1 if build_failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as exc:
        print("\nmkdocsify: %s\n" % exc, file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
