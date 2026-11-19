# EM extensions — the index

The **index** of the community packages and plugins of Extended Matrix that
can be downloaded and installed (decision D-12): one `index.json`, in the form
of Blender's
[Extension Listing API v1](https://developer.blender.org/docs/features/extensions/api_listing/v1/),
which the EM tools read as a **repository** — EMStudio's *Tools ▸ Extensions…*,
EM Tools for Blender, a script with `from s3dgraphy import em`.

> **Status.** The index exists and is generated. EMStudio reads a repository
> (row X2 of the extensions plan): *Tools ▸ Extensions… ▸ Repositories ▸
> + Add repository…*, the address of an `index.json` — this one, any other, a
> `file://` URL or a shared folder — with an optional access token and «Check
> for updates at start-up»; the archive is checked against `archive_hash`
> before it is opened, the `blocklist` is respected, `[requires]` are
> installed first. The same from a script (`em.extensions.add_repository`,
> `install_from`) and the command line (`python -m s3dgraphy.extensions repo
> add|sync|install`). An https repository is read only with «Allow online
> access» on (off by default). Side-by-side versions, «Update all» and the
> archives per platform (X3) are there too (`python -m s3dgraphy.extensions
> updates|update-all|versions|use|clean`, `build --split-platforms`; this
> index may list one archive per platform of the same id and version). EM
> Tools as a client (X6): not yet. The address below is not yet served.

**Address (once published):** `https://extendedmatrix.github.io/em-extensions/index.json`

## What is in the index

Every archive the index names is **built** from its sources by the CI and
served beside the index (`index.html` lists them to download or drag into
the Extensions window). The sources are two:

| from | what |
|---|---|
| [ExtendedMatrix/em-profiles](https://github.com/ExtendedMatrix/em-profiles) `profiles/<id>/`, at the commit in `sources.lock.json` | **community packages** — data only, or data with the code that serves them (mixed) |
| this repository, `plugins/<id>/` | **plugins** — code without data |

An entry carries Blender's fields (`id`, `version`, `name`, `tagline`,
`maintainer`, `type`, `license`, `archive_url`, `archive_hash`,
`archive_size`; `em_api_min` in place of `blender_version_min`) and ours:

- `sections` — for `data` and `code`, the version and the digest of each
  (a data-only update does not touch the code's), the vocabularies the data
  carry with their licence and tier, the code's hosts, platforms,
  permissions (each with its «why») and capabilities;
- `requires` — the archive's `[requires]`, as written;
- `content_hash` — the hash over the archive's files that an installation
  keeps in `installed.json`; `archive_hash` is the hash of the zip's bytes,
  checked after the download and before opening it;
- `reviewed` — who read the code (its digest), and when: from
  `reviewed.json` (row X4 fills it; a reviewed plugin will install without
  the second confirmation).

`blocklist.json` lists the ids withdrawn, with the reason the window shows;
a withdrawn id is never listed.

## How it is made

```
python tools/generate.py [--em-profiles ../em-profiles] [--check] [--lock] [--lang it]
```

1. every source folder is built with `python -m s3dgraphy.extensions build`
   — deterministic: the same folder gives the same bytes;
2. `python -m s3dgraphy.extensions server-generate` lists the archives —
   the one validator of the EM tools refuses what it refuses, and the
   repository what only a repository sees: a version of a section reused
   with another content, a vocabulary version with two contents, a
   vocabulary copied from the package that owns it, `requires` in a cycle;
3. `index.json` at the root is **committed**: a pull request shows the change
   of the index, hash by hash, to whoever reviews it. The CI runs
   `--check` and fails when the committed index is not the one the sources
   give; on `main` it publishes `dist/` to GitHub Pages.

A new version of a package in em-profiles reaches the index with a pull
request here that runs `tools/generate.py --lock` (the em-profiles commit in
`sources.lock.json`) and commits `index.json`.

## Other repositories

Anybody can serve a repository of their own — a project, a laboratory, a
NAS: put the archives in a folder and run

```
python -m s3dgraphy.extensions server-generate --repo-dir FOLDER [--html]
```

`archive_url` is then relative to the index, so the folder works the same
over HTTPS and as `file:///…/index.json` (decision D-13).

## Licences

See [LICENSING.md](LICENSING.md). Contributing a plugin:
[CONTRIBUTING.md](CONTRIBUTING.md).
