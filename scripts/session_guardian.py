#!/usr/bin/env python3
"""Optional, read-only Codex session monitor and handoff preparation. No daemon."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

SUPPORTED = {"0.154.0-alpha.6.2", "0.158.0-alpha.2.1", "0.159.2"}
MAX_LINE = 1024 * 1024
READ_BUDGET = 4 * MAX_LINE


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError, TypeError):
        return None


def positive(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def budget_metrics(used, window, policy, pending=0):
    """One lifecycle budget calculation shared by Hooks and the local panel."""
    room = min(policy["compact_limit"], window * 90 // 95) - used - pending
    remaining = (1 - (used + pending) / window) * 100
    gate = remaining <= 10 or room <= policy["handoff_reserve"] + policy["reaction_margin"]
    stage = "CONFIRM" if gate else "CLOSING" if remaining <= 20 else "CAUTION" if remaining <= 35 else "NORMAL"
    return room, remaining, stage


def locate(home: Path, thread: str) -> Path:
    """Internal fallback: exact thread lookup, never latest file or guessed cwd."""
    db = home / "state_5.sqlite"
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as conn:
        row = conn.execute("SELECT rollout_path FROM threads WHERE id = ?", (thread,)).fetchone()
    if not row or not row[0]:
        raise ValueError("No rollout for this exact thread; specify --rollout if verified.")
    return Path(row[0])


class RolloutReader:
    """Version-bounded fallback. Retains metrics only, never prompt/tool contents."""
    def __init__(self, thread: str, project: Path, observer=None):
        self.thread, self.project = thread, project.resolve()
        self.observer = observer
        self.identity = None
        self.offset = 0
        self.used = self.window = self.observed_at = None
        self.compactions = 0
        self.version = None
        self.partial_history = False
        self.invalidated = False
        self.discarding = False

    def poll(self, path: Path):
        with path.open("rb") as handle:
            st = os.fstat(handle.fileno())
            identity = (str(path.resolve()), st.st_dev, st.st_ino)
            if identity != self.identity or st.st_size < self.offset:
                self.__init__(self.thread, self.project, self.observer)
                raw = handle.readline(MAX_LINE + 1)
                if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
                    raise ValueError("Missing or oversized session metadata.")
                meta = json.loads(raw)
                if not isinstance(meta, dict) or not isinstance(meta.get("payload"), dict):
                    raise ValueError("Invalid session metadata shape.")
                info = meta.get("payload", {})
                if meta.get("type") != "session_meta" or info.get("id") != self.thread:
                    raise ValueError("Rollout identity differs from requested thread.")
                if not info.get("cwd") or Path(info["cwd"]).resolve() != self.project:
                    raise ValueError("Rollout cwd differs from explicit project; no project guessed.")
                self.version = info.get("cli_version")
                if self.version not in SUPPORTED:
                    raise ValueError("Unverified rollout version: " + str(self.version))
                self.identity = identity
                self.offset = handle.tell()
                # Bootstrap from a bounded tail, not the entire conversation.
                if st.st_size - self.offset > READ_BUDGET:
                    handle.seek(st.st_size - READ_BUDGET)
                    self.offset = handle.tell()
                    self.discarding = True
                    self.partial_history = True
            handle.seek(self.offset)
            read = 0
            while read < READ_BUDGET:
                start = handle.tell()
                raw = handle.readline(MAX_LINE + 1)
                if not raw:
                    break
                read += len(raw)
                if self.discarding or len(raw) > MAX_LINE:
                    # Discard incrementally, including records bigger than the read budget.
                    self.discarding = not raw.endswith(b"\n")
                    self.used = self.observed_at = None
                    self.invalidated = True
                    self.offset = handle.tell()
                    continue
                if not raw.endswith(b"\n"):
                    handle.seek(start)  # Writer has not completed this record yet.
                    break
                self.offset = handle.tell()
                try:
                    record = json.loads(raw)
                    if not isinstance(record, dict):
                        raise ValueError("record is not an object")
                    self.consume(record)
                    if self.observer is not None:
                        self.observer(record)
                except (ValueError, TypeError, AttributeError):
                    self.used = self.observed_at = None
                    self.invalidated = True
            # A backlog can contain a newer count: do not report old data as current.
            if read >= READ_BUDGET and handle.tell() < os.fstat(handle.fileno()).st_size:
                self.used = self.observed_at = None
                self.invalidated = True

    def consume(self, record):
        kind, data = record.get("type"), record.get("payload", {})
        if kind == "compacted":
            self.compactions += 1
            self.used = self.observed_at = None
        elif kind == "event_msg" and data.get("type") == "token_count":
            info = data.get("info")
            if not isinstance(info, dict):
                return  # Rate-limit-only notification, not a context sample.
            self.window = info.get("model_context_window")
            self.sample(info.get("last_token_usage", {}), record.get("timestamp"))
        elif kind == "token_usage_record":
            # Persisted per-response usage; cumulative thread/turn totals are NOT context.
            if data.get("thread_id") == self.thread:
                self.sample(data.get("usage", {}), record.get("timestamp"))

    def sample(self, usage, observed):
        used, at = usage.get("total_tokens"), timestamp(observed)
        if not positive(used) or at is None:
            self.used = self.observed_at = None
            self.invalidated = True
            return
        if self.observed_at is None or at >= self.observed_at:
            self.used, self.observed_at = used, at
            self.invalidated = False

    def status(self, *, now=None, max_age=300, caution=35, closing=20, emergency=10, compact_limit=None):
        now = time.time() if now is None else now
        result = {"schema": "acgm-session-status-v1", "state": "UNKNOWN",
                  "source": "codex-rollout-fallback", "quality": "UNKNOWN",
                  "cli_version": self.version, "context_used": self.used,
                  "context_window": self.window, "remaining_percent": None,
                  "observed_at": self.observed_at,
                  "compactions_in_observed_tail": self.compactions,
                  "history_complete": False, "stale": True}
        result["compact_limit"] = compact_limit
        result["boundary"] = "window-only" if compact_limit is None else "window-and-supplied-compact-limit"
        if not positive(self.window) or not positive(self.used) or self.observed_at is None:
            result["reason"] = "No validated context sample. Unknown is not healthy."
            return result
        age = now - self.observed_at
        if age < -60 or age > max_age or self.invalidated:
            result["reason"] = "Sample is stale, future-dated, or invalidated."
            return result
        ceiling = min(self.window, compact_limit) if positive(compact_limit) else self.window
        left = max(0, (1 - self.used / ceiling) * 100)
        result["effective_boundary_tokens"] = ceiling
        state = "EMERGENCY" if left <= emergency else "CLOSING" if left <= closing else "CAUTION" if left <= caution else "NORMAL"
        result.update(state=state, quality="OFFICIAL_ESTIMATE", stale=False,
                      remaining_percent=round(left, 1))
        if self.compactions:
            result["state"] = "DEGRADED"
            result["reason"] = "Compaction observed; this is not proof of information loss."
        return result


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, timeout=10)
    if result.returncode:
        raise ValueError("Git inspection failed: " + " ".join(args))
    return result.stdout.rstrip("\n")


def prepare(root: Path):
    """Mechanical facts only. A draft is not a verified handoff or a human decision."""
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise ValueError("Use the exact Git root for handoff preparation.")
    return {
        "schema": "acgm-session-handoff-preparation-v1", "status": "DRAFT",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "project": str(root.resolve()), "branch": git(root, "branch", "--show-current"),
        "head": git(root, "rev-parse", "HEAD"),
        "working_tree": git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        "instruction": "Use session-handoff skill. Recheck this non-atomic Git snapshot before acting. "
                       "Preserve existing handoff conventions, decisions and unfinished obligations. "
                       "Tests, deployment, authorization and completion require separate evidence. "
                       "No files were written and no tests or business operations were run.",
    }


def native_audit(project, thread, rollout):
    """Read-only reconciliation; native completions never arm or close a gate."""
    import acgm_codex as A
    session_id = A._opaque_readonly("session", thread)
    events = A._project_events(A._project_root(str(project)))
    events = [e for e in events if e.get("session_id") == session_id]
    results = {}
    def observe(record):
        data = record.get("payload", {})
        if record.get("type") != "event_msg" or data.get("type") != "item_completed" or data.get("thread_id") != thread:
            return
        item = data.get("item", {})
        if item.get("type") != "CommandExecution" or not item.get("id"):
            return
        call = A._opaque_readonly("call", item["id"])
        turn = A._opaque_readonly("turn", data.get("turn_id"))
        command = item.get("command", [])
        if not isinstance(command, list) or len(command) < 3 or command[-2] not in {"-c", "-lc"}:
            return
        operation = A._opaque_readonly("operation", command[-1])
        matches = [e for e in events if e.get("call_id") == call and e.get("turn_id") == turn and e.get("operation_id") == operation]
        if not matches:
            return
        from urllib.parse import urlparse, unquote
        cwd = item.get("cwd")
        if not isinstance(cwd, str):
            return
        cwd = unquote(urlparse(cwd).path) if cwd.startswith("file:") else cwd
        target = A._command_target_id(project, {"cwd":cwd}, command[-1], readonly=True)
        if any(e.get("target_id") and e.get("target_id") != target for e in matches):
            return
        results[(call, turn)] = {"call_id": call, "turn_id": turn,
            "outcome": A._execution_outcome({"tool_response":item}),
            "native_status": item.get("status"), "exit_code":item.get("exit_code"),
            "hook_event_ids":[e["event_id"] for e in matches]}
    reader = RolloutReader(thread, project, observe)
    reader.poll(rollout)
    requests = {(e.get("call_id"),e.get("turn_id")) for e in events if e.get("kind") == "tool-requested"}
    return {"schema":"acgm-native-audit-v1", "source":"verified-version-rollout-tail",
        "history_complete":False, "invalidated":reader.invalidated,
        "results":list(results.values()), "requests_without_native_completion":len(requests-results.keys()),
        "coverage":"Only matching native completions in the bounded tail; missing, denied before execution, "
                   "and interrupted requests stay unknown unless independently observed. No authorization or gate evidence."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "watch", "handoff", "resume", "audit"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--thread", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--rollout", type=Path)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--max-age", type=float, default=300)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--caution", type=float, default=35)
    parser.add_argument("--closing", type=float, default=20)
    parser.add_argument("--emergency", type=float, default=10)
    parser.add_argument("--compact-limit", type=int, help="Verified total-context compaction threshold; does not change Codex settings")
    args = parser.parse_args(argv)
    if not 0 < args.emergency < args.closing < args.caution < 100:
        parser.error("Require 0 < emergency < closing < caution < 100")
    if not 1 <= args.interval <= 60 or not 1 <= args.max_age <= 3600:
        parser.error("interval must be 1..60 seconds; max-age must be 1..3600 seconds")
    if args.compact_limit is not None and not positive(args.compact_limit):
        parser.error("compact-limit must be positive")
    if args.command in {"handoff", "resume"}:
        try:
            result = prepare(args.project)
            if args.command == "resume":
                result["instruction"] = ("Read project rules and the explicitly selected handoff. "
                    "Compare its root, branch, HEAD, uncommitted work and active operations with "
                    "this freshly inspected state. Follow references only for the current task. "
                    "Record unresolved discrepancies; a handoff is not renewed authorization. "
                    "Do not start/resume an agent process or choose the newest handoff by date.")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            print(json.dumps({"status": "UNKNOWN", "reason": str(exc)}))
            return 2
    if not args.thread:
        parser.error("An exact --thread or CODEX_THREAD_ID is required; no latest-session guessing")
    if args.command == "audit":
        import acgm_codex as A
        try:
            print(json.dumps(native_audit(args.project, args.thread, args.rollout or locate(args.codex_home, args.thread))))
            return 0
        except (OSError, ValueError, sqlite3.Error, A.RuntimeProblem) as exc:
            print(json.dumps({"state":"UNKNOWN", "reason":str(exc)}))
            return 2
    reader = RolloutReader(args.thread, args.project)
    previous = None
    try:
        while True:
            try:
                reader.poll(args.rollout or locate(args.codex_home, args.thread))
                result = reader.status(max_age=args.max_age, caution=args.caution,
                                       closing=args.closing, emergency=args.emergency,
                                       compact_limit=args.compact_limit)
            except (OSError, ValueError, sqlite3.Error) as exc:
                result = {"state": "UNKNOWN", "quality": "UNKNOWN", "reason": str(exc)}
                reader = RolloutReader(args.thread, args.project)
            key = (result["state"], result.get("reason"))
            if args.command == "status" or key != previous:
                print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.command == "status":
                return 2 if result["state"] == "UNKNOWN" else 0
            previous = key
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
