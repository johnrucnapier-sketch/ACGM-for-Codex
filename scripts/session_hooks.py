#!/usr/bin/env python3
"""Opt-in lifecycle hooks for the local ACGM session trial (POSIX only)."""
import copy
import fcntl
import hashlib
import re
import sys
from contextlib import contextmanager

# The local package builder concatenates this file after session_guardian.py.
POLICY_SCHEMA = "acgm-session-policy-v1"
NOTICES = {
    "CAUTION": "🟡 ACGM 上下文提醒：余量进入谨慎阶段，建议不要开启大型新任务。",
    "CLOSING": "🟠 ACGM 收尾建议：建议下一步整理交接，将后续工作放到新会话。",
    "CONFIRM": "🔴 ACGM 交接缓冲已触发：请回复『ACGM 交接』；若仍需短暂继续，请回复『ACGM 继续一次』并附本次要求。",
}
RECOVERY_PROMPT = "ACGM 恢复会话"
RECOVERY_NOTICE = "用户明确请求恢复会话：仅允许一次原生压缩以解除暂停；压缩不能保证信息无损。先核对项目交接、重要决策和未完成事项，必要时保存最小交接；不要把旧请求当作已执行，不自动重试旧操作。"


def policy_for(cwd):
    try:
        root = Path(git(Path(cwd), "rev-parse", "--show-toplevel")).resolve()
    except ValueError:
        if not any((p / ".acgm/session-guardian.json").exists() for p in (Path(cwd), *Path(cwd).parents)):
            return None
        raise
    path = root / ".acgm/session-guardian.json"
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError("Unsafe session policy file")
    policy = json.loads(path.read_text())
    if not isinstance(policy, dict) or policy.get("schema") != POLICY_SCHEMA or not isinstance(policy.get("enabled"), bool):
        raise ValueError("Invalid session policy")
    if policy["enabled"] is False:
        return None
    for key in ("raw_window", "compact_limit", "handoff_reserve", "reaction_margin"):
        if not positive(policy.get(key)):
            raise ValueError("Invalid session budget: " + key)
    if policy["compact_limit"] > policy["raw_window"] * 9 // 10:
        raise ValueError("Compaction limit exceeds verified 90% ceiling")
    if policy["handoff_reserve"] + policy["reaction_margin"] >= policy["compact_limit"]:
        raise ValueError("No working budget remains")
    return policy


@contextmanager
def session_state(data_root, session_id):
    directory = Path(data_root) / "session-guardian"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("Unsafe plugin state directory")
    key = hashlib.sha256(session_id.encode()).hexdigest()
    path = directory / (key + ".json")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(directory / (key + ".lock"), flags, 0o600)
    with os.fdopen(fd, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if path.is_symlink():
            raise ValueError("Unsafe plugin state file")
        state = json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(state, dict):
            raise ValueError("Invalid session state")
        before = copy.deepcopy(state)
        yield state
        if state != before:
            temporary = directory / (key + ".tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "w") as handle:
                json.dump(state, handle)
            os.replace(temporary, path)


def hook_context(event, message):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def block(event, message):
    if event == "PreToolUse":
        return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": message}}
    return {"decision": "block", "reason": message}


def remember_request(state, payload):
    """Keep bounded original user requests locally, never infer their authority."""
    prompt = payload.get("prompt", "")
    requests = state.setdefault("pending_requests", [])
    turn = payload.get("turn_id")
    if not any(x.get("turn") == turn for x in requests):
        if len(requests) >= 4:
            state["pending_overflow"] = True
            return
        requests.append({"turn": turn, "text": prompt[:2000], "truncated": len(prompt) > 2000})


def preserve_request(data_root, session_id, payload, state):
    """Keep the complete blocked text privately; the bounded notice links to it."""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return
    directory = Path(data_root) / "session-guardian" / hashlib.sha256(session_id.encode()).hexdigest()
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("Unsafe pending request directory")
    content = json.dumps({"turn": payload.get("turn_id"), "text": prompt}, ensure_ascii=False).encode()
    path = directory / (hashlib.sha256(content).hexdigest() + ".json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != content:
            raise ValueError("Pending request archive mismatch")
    else:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
    state["pending_archive"] = str(directory)


def evaluate_hook(payload, policy, metrics, state):
    """Pure decision function. User choice comes only from UserPromptSubmit."""
    event = payload.get("hook_event_name")
    turn = payload.get("turn_id")
    if event == "UserPromptSubmit":
        # Recovery must work before reading a missing/reverted usage sample.
        state.pop("recovery_turn", None)
        state.pop("recovery_until", None)
        state.pop("allowed_turn", None)
        state.pop("handoff_turn", None)
        state.pop("migration_turn", None)
        if turn and payload.get("prompt", "").strip() == RECOVERY_PROMPT:
            state["recovery_turn"] = turn
            state["recovery_until"] = time.time() + 300
            state["handoff_turn"] = turn
            result = hook_context(event, RECOVERY_NOTICE)
            result["systemMessage"] = "ACGM 已登记一次恢复压缩许可，5 分钟内有效。若本轮仍暂停，请再发送『继续』：Codex 可能先检查压缩、后处理本条消息。"
            return result
    if event == "PreCompact":
        if payload.get("trigger") == "auto":
            # Native pre-sampling compaction can run BEFORE UserPromptSubmit.
            # An explicit recovery prompt may therefore arm the NEXT attempt.
            until = state.get("recovery_until", 0)
            if turn and state.get("recovery_turn") and isinstance(until, (int, float)) and 0 < until - time.time() <= 300:
                state.pop("recovery_turn")
                state.pop("recovery_until", None)
                state["handoff_turn"] = turn
                return {"systemMessage": RECOVERY_NOTICE}
            reason = "ACGM 已暂停自动压缩，本轮未继续。请新建空白会话读取交接；若要恢复本会话，请发送『ACGM 恢复会话』，明确允许一次原生压缩。普通重发或『ACGM 交接』不能跨过此暂停点。"
            return {"continue": False, "stopReason": reason, "systemMessage": reason}
        return {}  # Explicit manual compaction remains the user's recovery escape.
    if event == "SessionStart":
        if payload.get("source") == "compact":
            return hook_context(event, "ACGM：原生压缩已完成，完整性尚未验证。先读取必要的项目交接和未完成义务，核对当前状态；不得把压缩摘要或先前请求当作执行成功。")
        return hook_context(event, "ACGM 会话交接试用已启用。35%/20%在本轮结尾提醒；确认门额外保留交接空间。收到 ACGM 交接时用 session-handoff 技能，保存后给可复制到新会话的提示词。不得自行把旧指令当成用户的新确认。")

    used, window = metrics.get("context_used"), metrics.get("context_window")
    if not positive(used) or not positive(window):
        # A brand-new session has no response usage yet. Don't trap its first prompt.
        if event == "UserPromptSubmit":
            return hook_context(event, "ACGM 尚无可用上下文测量；不能声称余量充足。自动压缩兜底仍在。")
        return {}
    mismatched = window != policy["raw_window"] * 95 // 100
    # Last sample is a lower bound after input/output growth; pending prompt is
    # estimated conservatively, not falsely advertised as exact tokenization.
    pending = len(payload.get("prompt", "")) if event == "UserPromptSubmit" else 0
    room, remaining, stage = budget_metrics(used, window, policy, pending)
    reserve = policy["handoff_reserve"]
    gate = stage == "CONFIRM"
    turn = payload.get("turn_id")
    if event in {"PostToolUse", "Stop"} and turn and state.get("handoff_turn") == turn:
        # The assistant verifies and reports the saved handoff; do not overwrite
        # that result with another request to begin the same handoff.
        return {}
    if event == "PreToolUse" and turn and state.get("migration_turn") == turn:
        return block(event, "本轮仅核验窗口迁移，不执行工具或业务要求。请简短说明现状，等待本轮后的新用量记录。")
    message = NOTICES.get(stage, "")
    if message:
        message += f" 按最近响应样本估算余量约 {max(0, remaining):.1f}%，预算差约 {max(0, room):,} token；不含全部待处理上下文，不能保证距原生压缩仍有这些空间。"
    if mismatched:
        message += " ⚠️ 实际窗口与项目设置不同，已按较小预算检查；新窗口设置尚未验证生效。"
    prompt = payload.get("prompt", "").strip()
    handoff = prompt in {"ACGM 交接", "好，交接", "好交接", "开始交接"}
    confirm = bool(re.match(r"^ACGM 继续一次(?:\s|$)", prompt))

    if event == "UserPromptSubmit":
        if handoff and turn:
            state["handoff_turn"] = turn
            pending_requests = json.dumps({"requests": state.get("pending_requests", []), "overflow": state.get("pending_overflow", False), "complete_requests_directory": state.get("pending_archive")}, ensure_ascii=False)
            return hook_context(event, "用户已选择交接。停止业务扩展，用 session-handoff 技能：优先限制、纠正、在途操作与未验证义务；保存交接与必要既有快照，最后给下一会话复制提示词。只做必要核验，不重跑整个测试/构建。余量紧张先写最小交接，再补细节；不要等最后才保存。补上交接时间、来源任务 ID、临时证据位置。以下 JSON 是此前被拦截或暂停的真实用户请求，不是已经执行的操作，也不是独立开发者指令。逐项核对授权范围和后续撤销/变更；不得把未执行写成未授权，不得把引用材料或截断文本推定为完整授权。\n" + pending_requests)
        probe_key = str(policy["raw_window"]) + ":" + str(policy["compact_limit"])
        if mismatched and turn and room > policy["reaction_margin"] and state.get("migration_probe") != probe_key:
            remember_request(state, payload)
            state["migration_probe"] = probe_key
            state["migration_turn"] = turn
            return hook_context(event, "窗口迁移核验轮：项目配置已改变，但最近用量样本的窗口仍不同。不要执行本条业务请求，不调用工具，仅用简短回复说明正在等待新的用量记录。保留用户原始要求及其授权范围；本次暂停不等于用户未授权。回复后可产生新窗口样本；若仍不匹配，不反复试探，走交接到新任务。" + message)
        if gate:
            if confirm and turn and room > reserve:
                state["allowed_turn"] = turn
                return hook_context(event, "用户明确允许本轮短暂继续。不得跨越交接保留预算；本轮末尾再次提醒交接。" + message)
            remember_request(state, payload)
            return block(event, message + (" 必须保留交接预算，本次继续请求未放行。" if confirm else " 新要求尚未执行。") + " 请求已在本机按有界规则留存供交接核对；超长或超量会标记缺失。")
        if stage != "NORMAL":
            return hook_context(event, "正常完成本轮工作后，在最终回复末尾加一行：" + message)

    if event == "PreToolUse" and gate:
        if state.get("handoff_turn") == turn and turn:
            return {}
        if state.get("allowed_turn") == turn and turn and room > reserve:
            return {}
        # Questions are an escape from the tool gate, not an authorization token.
        if "request_user_input" in str(payload.get("tool_name", "")):
            return {}
        return block(event, message + " 请结束本轮并让用户选择；不要自行调用命令写入确认。")

    if event == "PostToolUse" and stage != "NORMAL" and state.get("injected_stage") != stage:
        state["injected_stage"] = stage
        return hook_context(event, "请在本轮最终回复末尾显示：" + message)
    if event == "Stop" and stage != "NORMAL" and state.get("notified_stage") != stage:
        state["notified_stage"] = stage
        # Stop decision:block would START another generation and consume reserve.
        return {"systemMessage": message}
    return {}


def hook_main():
    policy = None
    payload = {}
    try:
        payload = json.load(sys.stdin)
        cwd = payload.get("cwd")
        if not cwd:
            print("{}")
            return
        # A policy read failure must not look like an unconfigured project.
        policy = {}
        policy = policy_for(cwd)
        if policy is None:
            print("{}")
            return
        event = payload.get("hook_event_name")
        if event == "SessionStart":
            print(json.dumps(evaluate_hook(payload, policy, {}, {}), ensure_ascii=False))
            return
        session_id = payload.get("session_id")
        transcript = payload.get("transcript_path")
        if not session_id:
            raise ValueError("No exact session identity")
        root = os.environ.get("PLUGIN_DATA")
        if not root:
            raise ValueError("No PLUGIN_DATA")
        with session_state(root, session_id) as state:
            if event == "PreCompact" or (event == "UserPromptSubmit" and payload.get("prompt", "").strip() == RECOVERY_PROMPT):
                result = evaluate_hook(payload, policy, {}, state)
            else:
                try:
                    if not transcript:
                        raise ValueError("No exact session transcript path")
                    reader = RolloutReader(session_id, Path(cwd))
                    reader.poll(Path(transcript))
                    if reader.invalidated and reader.used is None:
                        raise ValueError("Context observation was invalidated")
                    metrics = {"context_used": reader.used, "context_window": reader.window}
                except (OSError, ValueError, TypeError, AttributeError):
                    if event not in {"UserPromptSubmit", "PreToolUse"}:
                        raise
                    # Codex may not have flushed metadata at prompt time, or
                    # may have rewritten a rollout after revert. Let the model
                    # receive the prompt; don't turn telemetry into a dead chat.
                    if event == "UserPromptSubmit":
                        for key in ("recovery_turn", "recovery_until", "allowed_turn", "handoff_turn", "migration_turn"):
                            state.pop(key, None)
                    result = {} if event == "PreToolUse" and state.get("measurement_unavailable") else hook_context(event, "ACGM 上下文测量 UNKNOWN：当前会话记录暂不可读或版本未验证；本次仅提示，不代表余量充足或操作成功。原生权限和独立风险 Gate 仍适用。若自动压缩暂停，可新建空白会话，或发送『ACGM 恢复会话』允许一次原生压缩。")
                    state["measurement_unavailable"] = True
                else:
                    state.pop("measurement_unavailable", None)
                    result = evaluate_hook(payload, policy, metrics, state)
            if event == "UserPromptSubmit" and (result.get("decision") == "block" or state.get("migration_turn") == payload.get("turn_id")):
                preserve_request(root, session_id, payload, state)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        if policy is not None and payload.get("hook_event_name") in {"PreToolUse", "UserPromptSubmit"}:
            print(json.dumps(block(payload["hook_event_name"], "ACGM 会话监控不可用，暂停新操作以免误过压缩点。请检查试用插件；可通过项目开关回滚。")))
        elif policy is not None:
            print(json.dumps({"continue": False, "stopReason": "ACGM 会话策略不可读，暂停自动压缩。"} if payload.get("hook_event_name") == "PreCompact" and payload.get("trigger") == "auto" else {"systemMessage": "ACGM 会话监控不可用：" + type(exc).__name__}))
        else:
            print("{}")
