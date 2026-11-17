"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Checks: non-finite metrics; row count and duplicate (item, seed) pairs; the (item, seed) set
    and slice tags against the baseline; evaluator failures and None/missing grader values;
    metrics that do not match what the rows recompute to (a hand-edited report); and, when
    base_spec is given, the ratchet on metrics and slices (nothing may get looser)."""
    problems: list[str] = []
    rows, man = pr.get("rows") or [], pr.get("manifest") or {}

    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, (int, float)) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf is not a score)")

    want_rows = int(man.get("items", 0)) * len(man.get("seeds") or [])
    if len(rows) != want_rows:
        problems.append(f"{len(rows)} rows, manifest says {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want_rows}")
    pairs = Counter((r.get("item_id"), r.get("seed")) for r in rows)
    problems += [f"duplicate row {k}" for k, n in sorted(pairs.items(), key=str) if n > 1]
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(pairs) != base_pairs:
        gone, extra = sorted(base_pairs - set(pairs), key=str), sorted(set(pairs) - base_pairs, key=str)
        problems.append(f"(item, seed) set differs from the baseline: {len(gone)} missing, {len(extra)} extra")
    if sorted(man.get("seeds") or []) != sorted((base.get("manifest") or {}).get("seeds") or []):
        problems.append("manifest seeds differ from the baseline's")

    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for m in graded:
        n_missing = sum(1 for r in rows if r.get(m) is None)
        if n_missing:
            problems.append(f"{n_missing} row(s) have no value for graded metric {m} (a crashed grader drops out of the mean)")

    if rows and graded and not problems:
        ids = [m for m in graded if m in rows[0]]
        has_cost = any("cost" in r for r in rows)
        again = aggregate([{**r, "cost": r.get("cost", 0.0)} for r in rows], ids, k_values=spec.get("pass_k", []))
        for k, v in again.items():
            if k == "cost_per_success" and not has_cost:
                continue
            got = (pr.get("metrics") or {}).get(k)
            if isinstance(v, (int, float)) and isinstance(got, (int, float)) and abs(v - got) > 1e-3:
                problems.append(f"metric {k} = {got} but the rows recompute to {v} (report was edited)")

    pr_tags = {r.get("item_id"): sorted(r.get("slices") or []) for r in rows}
    base_tags = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows") or []}
    moved = sorted(i for i in pr_tags.keys() & base_tags.keys() if pr_tags[i] != base_tags[i])
    if moved:
        problems.append(f"slice tags differ from the baseline for {len(moved)} item(s), e.g. {moved[0]}")

    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _loosened(new: dict, old: dict, label: str) -> list[str]:
    out = []
    nth, oth = new.get("threshold", new), old.get("threshold", old)
    if "max" in oth and nth.get("max", math.inf) > oth["max"]:
        out.append(f"{label}: max rose from {oth['max']} to {nth.get('max')}")
    if "min" in oth and nth.get("min", -math.inf) < oth["min"]:
        out.append(f"{label}: min fell from {oth['min']} to {nth.get('min')}")
    if "max_increase" in oth and nth.get("max_increase", math.inf) > oth["max_increase"]:
        out.append(f"{label}: max_increase rose from {oth['max_increase']} to {nth.get('max_increase')}")
    if oth.get("no_significant_drop") and not nth.get("no_significant_drop"):
        out.append(f"{label}: no_significant_drop was dropped")
    if old.get("blocking") and not new.get("blocking"):
        out.append(f"{label}: blocking metric became non-blocking")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Same eval-set version: nothing may get looser, and nothing may disappear."""
    out = []
    now = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        if m["id"] not in now:
            out.append(f"metric {m['id']} was removed")
        else:
            out += _loosened(now[m["id"]], m, f"metric {m['id']}")
    now_s = {s["name"]: s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        if s["name"] not in now_s:
            out.append(f"slice {s['name']} was removed")
        else:
            if now_s[s["name"]].get("metric") != s.get("metric"):
                out.append(f"slice {s['name']}: metric changed")
            out += _loosened(now_s[s["name"]], s, f"slice {s['name']}")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        keys = sorted(set(a) & set(b))
        note, verdict = "", "ok"
        if not keys:
            verdict, val = "fail", None
            note = "slice has no items in the PR or the baseline"
        else:
            val = sum(a[k] for k in keys) / len(keys)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        sid = f"slice:{name}/{metric}"
        if verdict != "ok" and sl.get("blocking", True):
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("BLOCK" if sl.get("blocking", True) else "warn")
        shown = "n/a" if val is None else f"{val:.4f}"
        lines.append(f"  {sid:<34} {shown:<8} {json.dumps({k: sl[k] for k in ('min',) if k in sl}):<14} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
