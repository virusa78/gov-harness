# ADR-0015: A source is validated where it is recorded, not where it is used

## Status

Accepted — 2026-08-07

## Context

`init` took `--source` and wrote it into `.harness.lock` without looking at it.
It could afford to: the documented install uses `--from-dir`, which reads a
local directory and never consults the source at all. Only `sync` over the
network parsed the value, and it demanded `https://github.com/OWNER/REPO`.

The README documented the other spelling:

```bash
python3 ~/src/gov-harness/harness.py init \
  --source virusa78/gov-harness \
  --from-dir ~/src/gov-harness \
```

So the documented install produced a lock that the documented upgrade path
refuses. The pilot proved it on a real project, and a fresh `v0.9.0-rc.1`
install reproduced it:

```
$ python3 scripts/harness.py sync --to v0.9.0-rc.1
REFUSED: network source must be an https://github.com/OWNER/REPO URL   (exit 3)
```

The refusal is honest. It is also useless. It arrives at the first network
sync, which may be months after the install and in a different session, and it
describes the format it wants rather than the fact that the lock was written
wrong at install time. Nothing in the message points at the cause, so the
reader's first hypothesis is "the source moved", not "my install was broken
from the start".

This is the shape of defect this repository keeps finding: not a wrong answer,
but a correct answer given too late to be actionable.

## Decision

**Validate and normalize the source at install, and accept both spellings
forever.**

Two separate commitments, and they are not the same one:

- `normalize_source` runs in `init` and `select` **before any file is written**.
  An unusable source fails the install rather than being recorded. Nothing is
  half-installed: the check precedes the transaction.
- `parse_source_repo` accepts `OWNER/REPO` **and** the URL form. Locks written
  under the old README are already installed in real projects. Refusing the
  short form here would strand them on a source they cannot sync from — turning
  a documentation defect into a migration.

The lock records the canonical URL, so every new lock is uniform and no
consumer has to know which spelling they happened to type.

Validation is a character-class check on owner and repo, not just a split on
`/`. An SSH remote — `git@github.com:owner/repo.git` — splits into two
non-empty parts and would otherwise pass, then be pasted into a URL as an
owner. That was caught by testing the fix rather than by writing it.

## Consequences

A source that is wrong is now wrong immediately, at the moment and in the
session where it can be corrected by editing one flag.

`https://github.com/` is hard-coded, so a fork hosted elsewhere cannot be a
source. That was already true — `from_network` only ever spoke to GitHub's
release API — but it was implicit in a parser and is now explicit in a
refusal that names what was given.

Existing locks holding the short form keep working and are not rewritten. A
lock is a receipt; silently editing one to match a newer convention would make
the receipt something the harness authors rather than something it recorded.
