#!/usr/bin/env python3
"""Build a local opt-in ACGM add-on. Does not install or change Codex settings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(destination):
    destination.mkdir(parents=True, exist_ok=True)
    (destination / ".codex-plugin").mkdir(exist_ok=True)
    (destination / "hooks").mkdir(exist_ok=True)
    (destination / "scripts").mkdir(exist_ok=True)
    (destination / "bin").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "bin/acgm-session", destination / "bin/acgm-session")
    shutil.copy2(ROOT / "scripts/session_guardian.py", destination / "scripts/session_guardian.py")
    reader = (ROOT / "scripts/session_guardian.py").read_text()
    reader = reader.rsplit('\nif __name__ == "__main__":', 1)[0]
    content = (reader + '\n' + (ROOT / "scripts/session_hooks.py").read_text() + '\nif __name__ == "__main__":\n    hook_main()\n').encode()
    runtime = destination / "scripts/session_runtime.py"
    runtime.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    # Trust covers the exact runtime bytes, not a mutable Python file by path.
    program = (
        "import hashlib,os,sys\n"
        "p=os.path.join(os.environ['PLUGIN_ROOT'],'scripts','session_runtime.py')\n"
        "f=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))\n"
        f"b=os.read(f,{len(content)+1});os.close(f)\n"
        f"assert len(b)=={len(content)} and hashlib.sha256(b).hexdigest()=='{digest}', 'ACGM runtime integrity mismatch'\n"
        "exec(compile(b,p,'exec'),{'__name__':'__main__','__file__':p})"
    )
    # Publication verification checks this generated command via hooks/list.
    command = "python3 -c '" + program.replace("'", "'\"'\"'") + "'"
    hooks = {}
    for event in ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact"]:
        hooks[event] = [{"hooks": [{"type": "command", "command": command,
                                    "timeout": 10, "statusMessage": "ACGM 会话缓冲检查"}]}]
    (destination / "hooks/hooks.json").write_text(json.dumps({"hooks": hooks}, ensure_ascii=False, indent=2) + '\n')
    manifest = {
        "name": "acgm-session-guardian", "version": "0.1.0-local.1",
        "description": "Optional ACGM session budget and handoff trial; explicit per-project opt-in.",
        "skills": "./skills/", "author": {"name": "johnrucnapier-sketch"},
        "interface": {"displayName": "ACGM Session Guardian (Local Trial)",
                      "shortDescription": "提醒、确认与预留交接缓冲的本机试用模块",
                      "longDescription": "Optional per-project session reminders, buffered confirmation gates and evidence-led handoff. Local trial only.",
                      "developerName": "johnrucnapier-sketch", "category": "Productivity",
                      "capabilities": [], "defaultPrompt": "检查当前项目的会话余量并准备必要的交接。"},
    }
    (destination / ".codex-plugin/plugin.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    shutil.copytree(ROOT / "skills/session-handoff", destination / "skills/session-handoff", dirs_exist_ok=True)
    return {"destination": str(destination), "runtime_sha256": digest, "runtime_bytes": len(content)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.destination), indent=2))
