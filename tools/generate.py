#!/usr/bin/env python3
"""Generate the index of the EM extensions, as the CI does.

    python tools/generate.py [--em-profiles PATH] [--base-url URL] [--out DIR]
                             [--check] [--lock] [--lang en|it] [--json]

1. The archives come from two places: the community packages of
   ExtendedMatrix/em-profiles (``profiles/<id>/``, a checkout at the commit
   named in ``sources.lock.json``) and the plugins of this repository
   (``plugins/<id>/``, code without data).
2. Each folder is built with ``s3dgraphy.extensions.build`` (deterministic:
   the same folder gives the same bytes) into ``--out`` (``dist/``).
3. ``s3dgraphy.extensions.server_generate`` lists them in
   ``dist/index.json`` and ``dist/index.html``, in the form of Blender's
   Extension Listing API v1, with ``archive_url`` under ``--base-url`` and the
   ``blocklist.json`` and ``reviewed.json`` of this repository. It refuses
   what the one validator of the EM tools refuses, and what only a repository
   sees (a version reused, a vocabulary copied from its owner, a cycle).
4. ``dist/index.json`` is copied to ``index.json`` at the root, which is
   committed: a pull request shows the change of the index, hash by hash, to
   whoever reviews it. ``--check`` writes nothing at the root and fails when
   the committed index is not the one these sources give.

5. ``reviewed.json`` (row X4) is checked against decision D-6: a review is
   written by the **editor** (``"as": "editor"``, an owner of
   ``/reviewed.json`` in this repository's CODEOWNERS) or by a **curator of
   a package that requires the plugin** (``"as": "curator:<package>"``, an
   owner of ``/profiles/<package>/`` in em-profiles' CODEOWNERS, the package
   requiring the id — or being it, for a mixed package's own code); ``by`` is
   the GitHub handle (``@name``) CODEOWNERS knows; an author of a plugin of
   ``plugins/`` does not review it alone. Add a line with
   ``python -m s3dgraphy.extensions review add <archive> --reviewed . --by @you --as …``.

6. The signature (row X8): with ``--sign`` the archives and the index of
   ``dist/`` get their minisign ``.minisig`` (the secret key's text in the
   environment variable ``EM_EXTENSIONS_SIGNING_KEY``, a secret of the CI;
   ``--sign-key FILE`` on a curator's machine). When ``minisign.pub`` is
   committed at the root, ``--sign`` without a key is an error, and the
   signatures are verified with that public key before anything is
   published. The committed ``index.json`` is never signed itself: the
   signatures live beside it in ``dist/`` (``--check`` stays the same bytes).

``--lock`` writes the em-profiles commit of the checkout into
``sources.lock.json`` (refused when ``profiles/`` there has changes not
committed). Exit 1 on any error; warnings never fail.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
BASE_URL = "https://extendedmatrix.github.io/em-extensions/"
LOCK = "sources.lock.json"
#: X8 · the public key committed here, and where the CI's secret key comes from
PUBLIC_KEY = "minisign.pub"
KEY_ENV = "EM_EXTENSIONS_SIGNING_KEY"

#: this repository's own problems, in the two languages of the EM tools
MESSAGES = {
    "gen_no_profiles": ("{path}: not a checkout of em-profiles (no profiles/ folder)",
                        "{path}: non è una copia di em-profiles (manca la cartella profiles/)"),
    "gen_lock_differs": ("em-profiles is at {head}, sources.lock.json says {lock}: check out {lock}, or --lock",
                         "em-profiles è a {head}, sources.lock.json dice {lock}: porta la copia a {lock}, oppure --lock"),
    "gen_lock_dirty": ("em-profiles has changes not committed in profiles/: commit them before --lock",
                       "em-profiles ha modifiche non committate in profiles/: committale prima di --lock"),
    "gen_build": ("{where}: not built — {why}", "{where}: non costruito — {why}"),
    "gen_plugin_folder": ("plugins/{folder}: the folder must be named as the plugin id ({id})",
                          "plugins/{folder}: la cartella deve chiamarsi come l'id del plugin ({id})"),
    "gen_plugin_data": ("plugins/{folder}: an archive with data is a community package: it goes to em-profiles",
                        "plugins/{folder}: un archivio con dati è un pacchetto di comunità: va in em-profiles"),
    "gen_plugin_owners": ("plugins/{folder}: no line for /plugins/{folder}/ in .github/CODEOWNERS (its authors review it)",
                          "plugins/{folder}: manca la riga /plugins/{folder}/ in .github/CODEOWNERS (lo rivedono i suoi autori)"),
    "gen_id_twice": ("{id}: in em-profiles and in plugins/ — one id, one place",
                     "{id}: in em-profiles e in plugins/ — un id, un posto"),
    "gen_index_differs": ("index.json is not the index of these sources: run tools/generate.py and commit it",
                          "index.json non è l'indice di queste sorgenti: lancia tools/generate.py e committalo"),
    # X8 · the signature
    "gen_sign_no_key": ("--sign: no secret key ({env} is empty and no --sign-key): {pub} is committed, so the index must be signed",
                        "--sign: nessuna chiave segreta ({env} è vuota e manca --sign-key): {pub} è committata, quindi l'indice va firmato"),
    "gen_sign_unsigned": ("--sign: no secret key and no {pub} committed: the index is published unsigned",
                          "--sign: nessuna chiave segreta e nessuna {pub} committata: l'indice si pubblica senza firma"),
    "gen_sign_failed": ("the signature: {why}", "la firma: {why}"),
    "gen_sign_other_key": ("signed with the key {got}, but {pub} is the key {want}: the public key and the CI's secret do not match",
                           "firmato con la chiave {got}, ma {pub} è la chiave {want}: la chiave pubblica e il segreto della CI non vanno insieme"),
    # X4 · who may review (decision D-6)
    "gen_review_by": ("reviewed.json: {id}: by must be a GitHub handle (@name), not {by!r}",
                      "reviewed.json: {id}: by dev'essere un nome GitHub (@nome), non {by!r}"),
    "gen_review_as": ("reviewed.json: {id}: as must be editor or curator:<package>, not {as_!r}",
                      "reviewed.json: {id}: as dev'essere editor o curator:<pacchetto>, non {as_!r}"),
    "gen_review_not_editor": ("reviewed.json: {id}: {by} is not an owner of /reviewed.json in CODEOWNERS",
                              "reviewed.json: {id}: {by} non è tra i titolari di /reviewed.json in CODEOWNERS"),
    "gen_review_no_package": ("reviewed.json: {id}: the package {package} is not in em-profiles",
                              "reviewed.json: {id}: il pacchetto {package} non è in em-profiles"),
    "gen_review_not_curator": ("reviewed.json: {id}: {by} is not a curator of {package} (em-profiles CODEOWNERS)",
                               "reviewed.json: {id}: {by} non è un curatore di {package} (CODEOWNERS di em-profiles)"),
    "gen_review_not_required": ("reviewed.json: {id}: {package} does not require it: its curators do not review it",
                                "reviewed.json: {id}: {package} non lo richiede: non lo rivedono i suoi curatori"),
    "gen_review_self": ("reviewed.json: {id}: {by} is an author of plugins/{id}/: a second reader reviews it",
                        "reviewed.json: {id}: {by} è un autore di plugins/{id}/: lo rivede un secondo lettore"),
}


def say(code: str, lang: str, **params) -> str:
    en, it = MESSAGES[code]
    return (it if lang.startswith("it") else en).format(**params)


def problem(code: str, level: str = "error", **params) -> Dict:
    return {"code": code, "level": level, "en": say(code, "en", **params), "it": say(code, "it", **params)}


def folders(root: Path) -> List[Path]:
    """The archives of a folder: its sub-folders with an envelope or a profile."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")
                  and ((p / "em-extension.toml").is_file() or (p / "profile.json").is_file()))


def git(path: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "--no-optional-locks", "-C", str(path), *args], capture_output=True,
                             text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def read_lock(root: Path = None) -> Dict:
    f = (root or REPO) / LOCK
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def plugin_checks(root: Path, opened: Dict[Path, object]) -> List[Dict]:
    owners = ((root / ".github" / "CODEOWNERS").read_text(encoding="utf-8").split()
              if (root / ".github" / "CODEOWNERS").is_file() else [])
    out = []
    for path, pkg in opened.items():
        folder = path.name
        if pkg.id and pkg.id != folder:
            out.append(problem("gen_plugin_folder", folder=folder, id=pkg.id))
        if pkg.has_data:
            out.append(problem("gen_plugin_data", folder=folder))
        if f"/plugins/{folder}/" not in owners:
            out.append(problem("gen_plugin_owners", folder=folder))
    return out


def codeowners(root: Path) -> Dict[str, List[str]]:
    """``/path/`` → its owners, from ``.github/CODEOWNERS`` (comments skipped)."""
    f = root / ".github" / "CODEOWNERS"
    out: Dict[str, List[str]] = {}
    if not f.is_file():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        parts = line.split("#", 1)[0].split()
        if len(parts) >= 2:
            out[parts[0]] = [p for p in parts[1:] if p.startswith("@")]
    return out


def review_checks(root: Path, em_profiles: Path) -> List[Dict]:
    """X4 · every line of ``reviewed.json`` against decision D-6 (see the head)."""
    from s3dgraphy.profiles.package import open_package

    f = root / "reviewed.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except ValueError:
        return []   # the library says it (index_list_unreadable)
    rows = doc.get("reviewed") if isinstance(doc, dict) else doc
    ours, theirs = codeowners(root), codeowners(em_profiles)
    editors = set(ours.get("/reviewed.json") or [])
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        rid, by, as_ = str(r.get("id")), str(r.get("by") or ""), str(r.get("as") or "")
        if not re.match(r"^@[A-Za-z0-9][A-Za-z0-9-]*(/[A-Za-z0-9._-]+)?$", by):
            out.append(problem("gen_review_by", id=rid, by=by))
            continue
        if as_ == "editor":
            if by not in editors:
                out.append(problem("gen_review_not_editor", id=rid, by=by))
            continue
        if not as_.startswith("curator:") or not as_[len("curator:"):]:
            out.append(problem("gen_review_as", id=rid, as_=as_))
            continue
        pkg = as_[len("curator:"):]
        folder = em_profiles / "profiles" / pkg
        if not folder.is_dir():
            out.append(problem("gen_review_no_package", id=rid, package=pkg))
            continue
        if by not in (theirs.get(f"/profiles/{pkg}/") or []):
            out.append(problem("gen_review_not_curator", id=rid, by=by, package=pkg))
            continue
        try:
            req = open_package(folder).requires() if pkg != rid else {}
        except Exception:    # the build says what is wrong with the package
            req = {}
        wanted = {str(x.get("id")) for x in (req.get("extensions") or []) if isinstance(x, dict)}
        if pkg != rid and rid not in wanted:
            out.append(problem("gen_review_not_required", id=rid, package=pkg))
            continue
        if by in (ours.get(f"/plugins/{rid}/") or []):
            out.append(problem("gen_review_self", id=rid, by=by))
    return out


def sign_dist(root: Path, out: Path, key_text: Optional[str]) -> List[Dict]:
    """X8 · the .minisig of every archive and of the index of ``out``, then
    checked with the committed ``minisign.pub`` when there is one."""
    from s3dgraphy.extensions import signing
    pub = root / PUBLIC_KEY
    if not key_text:
        if pub.is_file():
            return [problem("gen_sign_no_key", env=KEY_ENV, pub=PUBLIC_KEY)]
        return [problem("gen_sign_unsigned", level="warning", pub=PUBLIC_KEY)]
    try:
        got = signing.sign_repository(out, key_text)
    except signing.SignatureError as exc:
        return [problem("gen_sign_failed", why=exc.problem.text("en"))]
    if not got["ok"]:
        return [problem("gen_sign_failed", why="; ".join(p["en"] for p in got["problems"]))]
    if pub.is_file():
        want = signing.parse_public_key(pub.read_text(encoding="utf-8"))
        if want.id != got["key_id"]:
            return [problem("gen_sign_other_key", got=got["key_id"], want=want.id, pub=PUBLIC_KEY)]
        v = signing.verify_repository(out, [want])
        if not v["ok"]:
            return [problem("gen_sign_failed", why="; ".join(p["en"] for p in v["problems"]))]
    return []


def generate(em_profiles: Path, *, root: Path = None, base_url: str = BASE_URL, out: Path = None,
             check: bool = False, lock: bool = False, sign: bool = False, sign_key: Optional[str] = None) -> Dict:
    from s3dgraphy.extensions import build, server_generate
    from s3dgraphy.profiles.package import open_package

    root = root or REPO
    out = out or root / "dist"
    res: Dict = {"problems": [], "built": [], "index": None, "ok": False}
    if not (em_profiles / "profiles").is_dir():
        res["problems"].append(problem("gen_no_profiles", path=str(em_profiles)))
        return res
    head = git(em_profiles, "rev-parse", "HEAD")
    if lock:
        if git(em_profiles, "status", "--porcelain", "--", "profiles"):
            res["problems"].append(problem("gen_lock_dirty"))
            return res
        (root / LOCK).write_text(json.dumps({"em-profiles": head}, indent=2) + "\n", encoding="utf-8")
    want = read_lock(root).get("em-profiles")
    if want and head and head != want:
        res["problems"].append(problem("gen_lock_differs", head=head[:12], lock=want[:12]))
    plugins = {p: open_package(p) for p in folders(root / "plugins")}
    res["problems"] += plugin_checks(root, plugins)
    res["problems"] += review_checks(root, em_profiles)
    sources = [(p, f"profiles/{p.name}") for p in folders(em_profiles / "profiles")] + \
              [(p, f"plugins/{p.name}") for p in plugins]
    ids: Dict[str, str] = {}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for path, where in sources:
        b = build(path, output_dir=out)
        if not b["ok"]:
            why = "; ".join(e["en"] for e in b["errors"] if e["code"] != "build_refused")
            why_it = "; ".join(e["it"] for e in b["errors"] if e["code"] != "build_refused")
            p = problem("gen_build", where=where, why=why)
            p["it"] = say("gen_build", "it", where=where, why=why_it)
            res["problems"].append(p)
            continue
        if b["id"] in ids and ids[b["id"]].split("/")[0] != where.split("/")[0]:
            res["problems"].append(problem("gen_id_twice", id=b["id"]))
        ids.setdefault(b["id"], where)
        res["built"].append({"where": where, "file": b["file"], "archive_hash": b["archive_hash"]})
    gen = server_generate(out, base_url=base_url, blocklist=root / "blocklist.json", reviewed=root / "reviewed.json",
                          html_page=True)
    res["index"] = gen["index"]
    res["listed"], res["refused"] = gen["listed"], gen["refused"]
    res["problems"] += gen["problems"]
    for x in gen["refused"]:
        res["problems"] += [p for p in x["errors"] if p not in gen["problems"]]
    if sign:
        res["problems"] += sign_dist(root, out, sign_key)
    committed = root / "index.json"
    text = (out / "index.json").read_text(encoding="utf-8")
    if check:
        same = committed.is_file() and committed.read_text(encoding="utf-8") == text
        if not same:
            res["problems"].append(problem("gen_index_differs"))
    else:
        committed.write_text(text, encoding="utf-8")
    res["ok"] = not any(p["level"] == "error" for p in res["problems"])
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the index of the EM extensions, as the CI does")
    ap.add_argument("--em-profiles", type=Path, default=REPO.parent / "em-profiles",
                    help="a checkout of ExtendedMatrix/em-profiles (default: beside this repository)")
    ap.add_argument("--base-url", default=BASE_URL, help=f"where the archives are served (default {BASE_URL})")
    ap.add_argument("--out", type=Path, default=REPO / "dist", help="the archives, index.json and index.html")
    ap.add_argument("--check", action="store_true", help="fail when the committed index.json is not this one")
    ap.add_argument("--lock", action="store_true", help="record the em-profiles commit in sources.lock.json")
    ap.add_argument("--sign", action="store_true",
                    help=f"sign dist/ (X8): the secret key from ${KEY_ENV} or --sign-key")
    ap.add_argument("--sign-key", type=Path, default=None, help="a minisign secret key file (a curator's machine)")
    ap.add_argument("--lang", default="en", choices=("en", "it"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    import os
    key = a.sign_key.read_text(encoding="utf-8") if a.sign_key else os.environ.get(KEY_ENV) or None
    res = generate(a.em_profiles, base_url=a.base_url, out=a.out, check=a.check, lock=a.lock,
                   sign=a.sign or bool(a.sign_key), sign_key=key)
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0 if res["ok"] else 1
    for x in res.get("listed") or []:
        print(f"OK   {x['file']}  {x['type']}")
    for p in res["problems"]:
        print(f"{'FAIL' if p['level'] == 'error' else 'note'} {p[a.lang]}")
    n = len((res["index"] or {}).get("data") or [])
    print((f"{n} entries" if a.lang == "en" else f"{n} voci") + (" — ok" if res["ok"] else ""), file=sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
