#!/usr/bin/env python3
"""Opt-in lifecycle hooks for the local ACGM session trial (POSIX only)."""
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


def policy_for(cwd):
    root = Path(git(Path(cwd), "rev-parse", "--show-toplevel")).resolve()
    path = root / ".acgm/session-guardian.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError("Unsafe session policy file")
    policy = json.loads(path.read_text())
    if policy.get("schema") != POLICY_SCHEMA or policy.get("enabled") is not True:
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
        before = dict(state)
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


def evaluate_hook(payload, policy, metrics, state):
    """Pure decision function. User choice comes only from UserPromptSubmit."""
    event = payload.get("hook_event_name")
    if event == "PreCompact":
        if payload.get("trigger") == "auto":
            return {"continue": False, "stopReason": "ACGM 已阻止自动压缩。当前会话余量不足以继续生成；请保留旧会话，在新会话读取已保存的交接及必要旧记录。",
                    "systemMessage": "🔴 自动压缩已暂停，未删除上下文。不要反复重试；必要时由你主动选择手动压缩。"}
        return {}  # Explicit manual compaction remains the user's recovery escape.
    if event == "SessionStart":
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
    compact = min(policy["compact_limit"], window * 90 // 95)
    room = compact - used - pending
    remaining = (1 - (used + pending) / window) * 100
    reserve = policy["handoff_reserve"]
    gate = remaining <= 10 or room <= reserve + policy["reaction_margin"]
    stage = "CONFIRM" if gate else "CLOSING" if remaining <= 20 else "CAUTION" if remaining <= 35 else "NORMAL"
    turn = payload.get("turn_id")
    message = NOTICES.get(stage, "")
    if message:
        message += f" 当前可用窗口余量约 {max(0, remaining):.1f}%；距压缩阈值约 {max(0, room):,} token（估计）。"
    if mismatched:
        message += " ⚠️ 实际窗口与项目设置不同，已按较小预算检查；新窗口设置尚未验证生效。"
    prompt = payload.get("prompt", "").strip()
    handoff = prompt in {"ACGM 交接", "好，交接", "好交接", "开始交接"}
    confirm = bool(re.match(r"^ACGM 继续一次(?:\s|$)", prompt))

    if event == "UserPromptSubmit":
        state.pop("allowed_turn", None)
        state.pop("handoff_turn", None)
        if handoff and turn:
            state["handoff_turn"] = turn
            return hook_context(event, "用户已选择交接。停止业务扩展，用 session-handoff 技能：优先限制、纠正、在途操作与未验证义务；保存交接与必要既有快照，最后给下一会话复制提示词。只做必要核验，不重跑整个测试/构建。余量紧张先写最小交接，再补细节；不要等最后才保存。")
        if gate:
            if confirm and turn and room > reserve:
                state["allowed_turn"] = turn
                return hook_context(event, "用户明确允许本轮短暂继续。不得跨越交接保留预算；本轮末尾再次提醒交接。" + message)
            return block(event, message + (" 必须保留交接预算，本次继续请求未放行。" if confirm else " 新要求尚未执行。"))
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
        policy = policy_for(cwd)
        if policy is None:
            print("{}")
            return
        event = payload.get("hook_event_name")
        if event in {"PreCompact", "SessionStart"}:
            print(json.dumps(evaluate_hook(payload, policy, {}, {}), ensure_ascii=False))
            return
        session_id = payload.get("session_id")
        transcript = payload.get("transcript_path")
        if not session_id or not transcript:
            raise ValueError("No exact session transcript identity")
        reader = RolloutReader(session_id, Path(cwd))
        reader.poll(Path(transcript))
        if reader.invalidated and reader.used is None:
            raise ValueError("Context observation was invalidated")
        metrics = {"context_used": reader.used, "context_window": reader.window}
        root = os.environ.get("PLUGIN_DATA")
        if not root:
            raise ValueError("No PLUGIN_DATA")
        with session_state(root, session_id) as state:
            result = evaluate_hook(payload, policy, metrics, state)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        if policy is not None and payload.get("hook_event_name") in {"PreToolUse", "UserPromptSubmit"}:
            print(json.dumps(block(payload["hook_event_name"], "ACGM 会话监控不可用，暂停新操作以免误过压缩点。请检查试用插件；可通过项目开关回滚。")))
        elif policy is not None:
            print(json.dumps({"systemMessage": "ACGM 会话监控不可用：" + type(exc).__name__}))
        else:
            print("{}")
