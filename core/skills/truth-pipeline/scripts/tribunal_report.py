#!/usr/bin/env python3
"""
tribunal_report.py — window certifier for the truth-pipeline shadow rollout.

Reads an append-only JSONL tribunal journal, validates every record, resolves
each divergence to its LAST valid classification, replays the waves in order,
and prints SATISFIED / UNSATISFIED for the flip gate.

Window semantics (from SKILL.md, Stage 4/5):

    clean wave    = measured AND not tamper_unresolved
                    AND (matched OR all its divergences excused)
    excused       = only by record: disposition "excused" with either
                       excuse_kind "sentinel_bug" AND replay "green", or
                       excuse_kind "delta_class" AND window_config.deltas_signed
    unknown        -> resets the streak
    pending        -> resets the streak
    not measured   -> does NOT count and does NOT reset (a crashed run != a wave)
    corrupt line   -> FAIL_CLOSED, the whole window cannot be certified
    not recorded   -> does not exist

Flip is licensed (SATISFIED) only when ALL hold:
    * a window_config exists and precedes every wave (N recorded before the
      window starts — never chosen after peeking at the counter)
    * poison corpus green
    * declared delta-classes signed
    * trailing clean-wave streak >= N   (a dead streak does not resurrect)
    * zero unresolved tamper in the counted streak (enforced by reset)

Exit codes:
    0  SATISFIED
    1  UNSATISFIED
    2  usage error (journal not found / not readable)
    3  FAIL_CLOSED (corrupt or ambiguous journal)

This is the copy-paste skeleton. It fixes window semantics and makes
fail-closed cheaper than self-deception. It does NOT replace tamper-proof
storage, signatures, code owners, or review. In particular it does NOT enforce
solo-mode separation (executor must not excuse its own divergence in the same
pass) — that needs pass/commit provenance the minimal journal does not carry.
Law 14: never call this an independent tribunal.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

KNOWN_TYPES = {"window_config", "wave", "classification"}


class FailClosed(Exception):
    """Raised on any corrupt/ambiguous record. The window cannot be certified."""


@dataclass
class WindowConfig:
    n: int
    poison_green: bool
    deltas_signed: bool


@dataclass
class Wave:
    wave_id: str
    measured: bool
    matched: bool
    divergences: list
    tamper_unresolved: bool


@dataclass
class Result:
    verdict: str                       # "SATISFIED" | "UNSATISFIED"
    n: int
    trailing_streak: int
    gates: dict
    reasons: list = field(default_factory=list)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise FailClosed(msg)


def _is_bool(v) -> bool:
    return isinstance(v, bool)


def parse_records(lines):
    """Parse and structurally validate. Corruption -> FailClosed.

    Returns (configs, waves, classifications, wave_before_config).
    """
    configs, waves, classifications = [], [], []
    seen_wave_ids = set()
    wave_before_config = False

    for ln, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue  # blank lines are allowed and ignored
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            raise FailClosed(f"line {ln}: invalid JSON")
        _require(isinstance(rec, dict), f"line {ln}: record is not an object")
        rtype = rec.get("type")
        _require(isinstance(rtype, str) and rtype in KNOWN_TYPES,
                 f"line {ln}: unknown or missing record type {rtype!r}")

        if rtype == "window_config":
            n = rec.get("n")
            _require(isinstance(n, int) and not isinstance(n, bool) and n > 0,
                     f"line {ln}: window_config.n must be a positive integer")
            _require(_is_bool(rec.get("poison_green")),
                     f"line {ln}: window_config.poison_green must be bool")
            _require(_is_bool(rec.get("deltas_signed")),
                     f"line {ln}: window_config.deltas_signed must be bool")
            configs.append(WindowConfig(n, rec["poison_green"], rec["deltas_signed"]))

        elif rtype == "wave":
            wid = rec.get("wave_id")
            _require(isinstance(wid, str) and wid, f"line {ln}: wave.wave_id must be a non-empty string")
            _require(wid not in seen_wave_ids, f"line {ln}: duplicate wave_id {wid!r} (ambiguous journal)")
            seen_wave_ids.add(wid)
            _require(_is_bool(rec.get("measured")), f"line {ln}: wave.measured must be bool")
            _require(_is_bool(rec.get("matched")), f"line {ln}: wave.matched must be bool")
            _require(_is_bool(rec.get("tamper_unresolved")), f"line {ln}: wave.tamper_unresolved must be bool")
            divs = rec.get("divergences", [])
            _require(isinstance(divs, list) and all(isinstance(d, str) for d in divs),
                     f"line {ln}: wave.divergences must be a list of strings")
            if not configs:
                wave_before_config = True
            waves.append(Wave(wid, rec["measured"], rec["matched"], divs, rec["tamper_unresolved"]))

        elif rtype == "classification":
            did = rec.get("divergence_id")
            _require(isinstance(did, str) and did, f"line {ln}: classification.divergence_id required")
            disp = rec.get("disposition")
            _require(isinstance(disp, str) and disp, f"line {ln}: classification.disposition required")
            classifications.append(rec)  # keep raw; last-valid-wins resolved later

    return configs, waves, classifications, wave_before_config


def resolve_excused(classifications, config: WindowConfig):
    """Last valid classification per divergence_id wins. Return set of excused ids."""
    final = {}
    for rec in classifications:
        final[rec["divergence_id"]] = rec  # later overrides earlier
    excused = set()
    for did, rec in final.items():
        if rec.get("disposition") != "excused":
            continue  # pending / unknown / anything else -> not excused
        kind = rec.get("excuse_kind")
        if kind == "sentinel_bug" and rec.get("replay") == "green":
            excused.add(did)
        elif kind in ("delta_class", "delta-class") and config.deltas_signed:
            excused.add(did)
        # any other excuse (missing kind, sentinel_bug w/o green replay,
        # delta_class w/o signed deltas) is NOT a valid excuse -> stays unexcused
    return excused


def trailing_clean_streak(waves, excused):
    """Replay waves in order; return the trailing consecutive clean-wave count."""
    streak = 0
    for w in waves:
        if not w.measured:
            continue  # not measured: doesn't count, doesn't reset
        clean = (not w.tamper_unresolved) and (w.matched or all(d in excused for d in w.divergences))
        streak = streak + 1 if clean else 0
    return streak


def evaluate(lines) -> Result:
    configs, waves, classifications, wave_before_config = parse_records(lines)

    reasons = []
    if not configs:
        return Result("UNSATISFIED", 0, 0,
                      {"window_config_present": False}, ["no window_config recorded"])

    config = configs[0]
    excused = resolve_excused(classifications, config)
    streak = trailing_clean_streak(waves, excused)

    gates = {
        "window_config_before_waves": not wave_before_config,
        "poison_green": config.poison_green,
        "deltas_signed": config.deltas_signed,
        f"trailing_streak>=N({config.n})": streak >= config.n,
    }
    if wave_before_config:
        reasons.append("a wave precedes the first window_config (N chosen after peeking)")
    if not config.poison_green:
        reasons.append("poison corpus not green")
    if not config.deltas_signed:
        reasons.append("declared delta-classes not signed")
    if streak < config.n:
        reasons.append(f"trailing clean-wave streak {streak} < required N={config.n}")

    verdict = "SATISFIED" if all(gates.values()) else "UNSATISFIED"
    return Result(verdict, config.n, streak, gates, reasons)


def format_report(result: Result) -> str:
    out = ["── Tribunal window report ─────────────────────────────"]
    out.append(f"  N (required clean waves)   : {result.n}")
    out.append(f"  trailing clean-wave streak : {result.trailing_streak}")
    out.append("  gates:")
    for name, ok in result.gates.items():
        out.append(f"    {'PASS' if ok else 'FAIL'}  {name}")
    if result.reasons:
        out.append("  reasons:")
        for r in result.reasons:
            out.append(f"    - {r}")
    out.append(f"  VERDICT: {result.verdict}")
    return "\n".join(out)


def run_file(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as e:
        print(f"error: cannot read journal {path!r}: {e}", file=sys.stderr)
        return 2
    try:
        result = evaluate(lines)
    except FailClosed as e:
        print("── Tribunal window report ─────────────────────────────")
        print(f"  FAIL_CLOSED: {e}")
        print("  VERDICT: FAIL_CLOSED (window cannot be certified)")
        return 3
    print(format_report(result))
    return 0 if result.verdict == "SATISFIED" else 1


def _selftest() -> int:
    """Self-verify the done-criterion: UNSATISFIED before the window, SATISFIED after."""
    cfg = '{"type":"window_config","n":2,"poison_green":true,"deltas_signed":true}'
    clean = '{{"type":"wave","wave_id":"{w}","measured":true,"matched":true,"divergences":[],"tamper_unresolved":false}}'

    def ev(lines):
        return evaluate(lines)

    cases = []
    # before the window: one clean wave, N=2
    cases.append(("before-window", ev([cfg, clean.format(w="W1")]).verdict == "UNSATISFIED"))
    # after the window: two clean waves
    cases.append(("after-window", ev([cfg, clean.format(w="W1"), clean.format(w="W2")]).verdict == "SATISFIED"))
    # divergence excused by sentinel_bug + green replay counts as clean
    cases.append(("excused", ev([
        cfg,
        '{"type":"wave","wave_id":"W1","measured":false,"matched":false,"divergences":[],"tamper_unresolved":false}',
        '{"type":"wave","wave_id":"W2","measured":true,"matched":false,"divergences":["D1"],"tamper_unresolved":false}',
        '{"type":"classification","divergence_id":"D1","disposition":"excused","excuse_kind":"sentinel_bug","replay":"green"}',
        clean.format(w="W3"),
    ]).verdict == "SATISFIED"))
    # pending divergence resets the streak
    cases.append(("pending-resets", ev([
        cfg, clean.format(w="W1"),
        '{"type":"wave","wave_id":"W2","measured":true,"matched":false,"divergences":["D1"],"tamper_unresolved":false}',
        '{"type":"classification","divergence_id":"D1","disposition":"pending","root_cause":"unknown"}',
        clean.format(w="W3"),
    ]).verdict == "UNSATISFIED"))
    # not-measured wave does not reset a streak
    cases.append(("crash-not-reset", ev([
        cfg, clean.format(w="W1"),
        '{"type":"wave","wave_id":"WX","measured":false,"matched":false,"divergences":[],"tamper_unresolved":false}',
        clean.format(w="W2"),
    ]).verdict == "SATISFIED"))
    # tamper resets even if matched
    cases.append(("tamper-resets", ev([
        cfg, clean.format(w="W1"),
        '{"type":"wave","wave_id":"W2","measured":true,"matched":true,"divergences":[],"tamper_unresolved":true}',
        clean.format(w="W3"),
    ]).verdict == "UNSATISFIED"))
    # corrupt line fails closed
    corrupt_failed = False
    try:
        ev([cfg, "{not json"])
    except FailClosed:
        corrupt_failed = True
    cases.append(("corrupt-fail-closed", corrupt_failed))
    # wave before config is not certifiable
    cases.append(("wave-before-config", ev([clean.format(w="W1"), cfg, clean.format(w="W2")]).verdict == "UNSATISFIED"))

    ok = True
    for name, passed in cases:
        print(f"  {'ok  ' if passed else 'FAIL'} {name}")
        ok = ok and passed
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Certify a truth-pipeline tribunal window.")
    ap.add_argument("journal", nargs="?", default=".tribunal.jsonl",
                    help="path to the append-only JSONL journal (default: .tribunal.jsonl)")
    ap.add_argument("--selftest", action="store_true", help="run built-in semantic self-tests and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run_file(args.journal)


if __name__ == "__main__":
    sys.exit(main())
