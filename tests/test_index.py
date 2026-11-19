"""The checks every pull request must pass (the CI runs them, and tools/generate.py)."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import generate  # noqa: E402

X = pytest.importorskip("s3dgraphy.extensions")
EM_PROFILES = REPO.parent / "em-profiles"
EXAMPLES = EM_PROFILES / "examples"
needs_examples = pytest.mark.skipif(not EXAMPLES.is_dir(), reason="em-profiles is not beside this repository")


@pytest.fixture
def frame(tmp_path):
    """A copy of this repository's frame and a fake em-profiles checkout,
    where the test puts packages and plugins."""
    root = tmp_path / "em-extensions"
    root.mkdir()
    for n in ("blocklist.json", "reviewed.json"):
        shutil.copy(REPO / n, root / n)
    (root / "plugins").mkdir()
    (root / ".github").mkdir()
    (root / ".github" / "CODEOWNERS").write_text("/tools/ @zalmoxes-laran\n", encoding="utf-8")
    emp = tmp_path / "em-profiles"
    (emp / "profiles").mkdir(parents=True)
    return root, emp


def _codes(res, level="error"):
    return sorted(p["code"] for p in res["problems"] if p["level"] == level)


def test_the_committed_index_is_a_listing_api_v1_index():
    doc = json.loads((REPO / "index.json").read_text(encoding="utf-8"))
    assert doc["version"] == "v1" and isinstance(doc["blocklist"], list) and isinstance(doc["data"], list)
    assert X.validate_index(doc).ok
    lock = json.loads((REPO / "sources.lock.json").read_text(encoding="utf-8"))
    assert re.match(r"^[0-9a-f]{40}$", lock["em-profiles"])


@pytest.mark.skipif(not (EM_PROFILES / "profiles").is_dir(), reason="em-profiles is not beside this repository")
def test_the_committed_index_is_the_one_the_sources_give(tmp_path):
    """What the CI checks (there, em-profiles is checked out at the lock)."""
    head = generate.git(EM_PROFILES, "rev-parse", "HEAD")
    if head != generate.read_lock().get("em-profiles"):
        pytest.skip("the em-profiles beside this one is not at the commit of sources.lock.json")
    res = generate.generate(EM_PROFILES, out=tmp_path / "dist", check=True)
    assert res["ok"], res["problems"]


@needs_examples
def test_packages_and_plugins_listed_with_their_sections(frame, tmp_path):
    root, emp = frame
    shutil.copytree(EXAMPLES / "esempio-statuaria", emp / "profiles" / "esempio-statuaria")
    shutil.copytree(EXAMPLES / "facemesh_fit", root / "plugins" / "facemesh_fit")
    (root / ".github" / "CODEOWNERS").write_text("/plugins/facemesh_fit/ @zalmoxes-laran\n", encoding="utf-8")
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert res["ok"], res["problems"]
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))["data"]
    assert [(e["id"], e["type"]) for e in data] == [("esempio-statuaria", "community-package"), ("facemesh_fit", "plugin")]
    assert data[0]["archive_url"] == generate.BASE_URL + "esempio-statuaria-0.1.0.zip"
    assert set(data[0]["sections"]) == {"data"} and set(data[1]["sections"]) == {"code"}
    assert (tmp_path / "dist" / "index.html").is_file() and (tmp_path / "dist" / "facemesh_fit-0.3.0.zip").is_file()
    # the same sources, the same bytes: --check passes; a hand-edited index does not
    assert generate.generate(emp, root=root, out=tmp_path / "dist", check=True)["ok"]
    (root / "index.json").write_text((root / "index.json").read_text(encoding="utf-8").replace("0.1.0", "0.1.9"),
                                     encoding="utf-8")
    res = generate.generate(emp, root=root, out=tmp_path / "dist", check=True)
    assert _codes(res) == ["gen_index_differs"]


@needs_examples
def test_the_place_of_a_plugin(frame, tmp_path):
    root, emp = frame
    shutil.copytree(EXAMPLES / "facemesh_fit", root / "plugins" / "facemesh")       # folder ≠ id, no owners
    shutil.copytree(EXAMPLES / "esempio-statuaria", root / "plugins" / "esempio-statuaria")  # data: not here
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert _codes(res) == ["gen_plugin_data", "gen_plugin_folder", "gen_plugin_owners", "gen_plugin_owners"]
    assert not res["ok"]


@needs_examples
def test_what_only_a_repository_sees_fails_the_index(frame, tmp_path):
    """The two forms of the synthetic example in one repository: the mixed
    one carries data 0.1.0 with another content (its profile.json does not
    offer facemesh_fit, the other does): the same version, two contents."""
    root, emp = frame
    shutil.copytree(EXAMPLES / "esempio-statuaria", emp / "profiles" / "esempio-statuaria")
    shutil.copytree(EXAMPLES / "esempio-statuaria-misto", emp / "profiles" / "esempio-statuaria-misto")
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert "index_section_reused" in _codes(res)
    assert [e["version"] for e in res["index"]["data"]] == ["0.1.0"]


@needs_examples
def test_blocklist_and_reviewed_come_from_this_repository(frame, tmp_path):
    root, emp = frame
    shutil.copytree(EXAMPLES / "facemesh_fit", root / "plugins" / "facemesh_fit")
    (root / ".github" / "CODEOWNERS").write_text("/plugins/facemesh_fit/ @autore\n/reviewed.json @zalmoxes-laran\n",
                                                 encoding="utf-8")
    code = X.index_entry(None, blob=_zip(EXAMPLES / "facemesh_fit", tmp_path), archive_url="x")[0]["sections"]["code"]
    (root / "reviewed.json").write_text(json.dumps({"reviewed": [
        {"id": "facemesh_fit", "digest": code["digest"], "by": "@zalmoxes-laran", "as": "editor", "on": "2026-11-19"}]}),
        encoding="utf-8")
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert res["ok"], res["problems"]
    assert res["index"]["data"][0]["reviewed"]["by"] == "@zalmoxes-laran"
    assert res["index"]["data"][0]["reviewed"]["as"] == "editor"
    (root / "blocklist.json").write_text(json.dumps({"blocklist": [
        {"id": "facemesh_fit", "reason": "example withdrawn", "reason_it": "esempio ritirato"}]}), encoding="utf-8")
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert res["ok"] and res["index"]["data"] == [] and res["index"]["blocklist"][0]["reason_it"] == "esempio ritirato"


@needs_examples
def test_who_may_review_follows_d6(frame, tmp_path):
    """X4 · the editor, or a curator of a package that requires the plugin;
    never its author alone; by the GitHub handle CODEOWNERS knows."""
    root, emp = frame
    shutil.copytree(EXAMPLES / "facemesh_fit", root / "plugins" / "facemesh_fit")
    shutil.copytree(EXAMPLES / "esempio-statuaria", emp / "profiles" / "esempio-statuaria")
    shutil.copytree(EXAMPLES / "example-toolmarks", emp / "profiles" / "example-toolmarks")
    (root / ".github" / "CODEOWNERS").write_text(
        "/reviewed.json @zalmoxes-laran\n/plugins/facemesh_fit/ @autore @curatrice\n", encoding="utf-8")
    (emp / ".github").mkdir()
    (emp / ".github" / "CODEOWNERS").write_text(
        "/profiles/esempio-statuaria/ @curatrice @curatore\n/profiles/example-toolmarks/ @altro\n", encoding="utf-8")
    digest = X.review_digest(EXAMPLES / "facemesh_fit")["digest"]

    def with_rows(*rows):
        (root / "reviewed.json").write_text(json.dumps({"reviewed": [
            dict(id="facemesh_fit", digest=digest, on="2026-11-19", **r) for r in rows]}), encoding="utf-8")
        return generate.review_checks(root, emp)

    assert with_rows({"by": "@zalmoxes-laran", "as": "editor"}) == []
    assert with_rows({"by": "@curatore", "as": "curator:esempio-statuaria"}) == []
    codes = lambda ps: sorted(p["code"] for p in ps)
    assert codes(with_rows({"by": "orcid:0000-0002-1825-0097", "as": "editor"})) == ["gen_review_by"]
    assert codes(with_rows({"by": "@curatore", "as": "editor"})) == ["gen_review_not_editor"]
    assert codes(with_rows({"by": "@curatore"})) == ["gen_review_as"]
    assert codes(with_rows({"by": "@curatore", "as": "curator:nessuno"})) == ["gen_review_no_package"]
    assert codes(with_rows({"by": "@altro", "as": "curator:esempio-statuaria"})) == ["gen_review_not_curator"]
    assert codes(with_rows({"by": "@altro", "as": "curator:example-toolmarks"})) == ["gen_review_not_required"]
    # a curator who is also an author of the plugin does not review it alone
    ps = with_rows({"by": "@curatrice", "as": "curator:esempio-statuaria"})
    assert codes(ps) == ["gen_review_self"] and "secondo lettore" in ps[0]["it"]
    # the whole generation fails on it
    res = generate.generate(emp, root=root, out=tmp_path / "dist")
    assert not res["ok"] and "gen_review_self" in _codes(res)


def _zip(folder: Path, tmp_path: Path) -> bytes:
    out = tmp_path / "z"
    out.mkdir(exist_ok=True)
    return Path(X.build(folder, output_dir=out)["path"]).read_bytes()


def test_not_a_checkout_and_the_lock(frame, tmp_path):
    root, emp = frame
    res = generate.generate(tmp_path / "nothing", root=root)
    assert _codes(res) == ["gen_no_profiles"]


def test_every_message_in_english_and_italian():
    for code, (en, it) in generate.MESSAGES.items():
        assert en and it and en != it, code
        assert set(re.findall(r"{(\w+)}", en)) == set(re.findall(r"{(\w+)}", it)), code


def test_the_command_line_says_it_in_both_languages(frame, tmp_path, capsys, monkeypatch):
    root, emp = frame
    monkeypatch.setattr(generate, "REPO", root)
    assert generate.main(["--em-profiles", str(tmp_path / "nothing"), "--lang", "it"]) == 1
    assert "non è una copia di em-profiles" in capsys.readouterr().out
    assert generate.main(["--em-profiles", str(emp), "--out", str(tmp_path / "d"), "--lang", "it"]) == 0
    assert "0 voci" in capsys.readouterr().err
