#!/usr/bin/env python3
"""Build a local opt-in ACGM add-on. Does not install or change Codex settings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def integrated_guardian_command():
    # Verify both source files before executing either. Reuse the tested trial
    # concatenation without shipping a second copy of the reader/state machine.
    sources = []
    for name in ("session_guardian.py", "session_hooks.py"):
        content = (ROOT / "scripts" / name).read_bytes()
        sources.append((name, len(content), hashlib.sha256(content).hexdigest()))
    program = (
        "import hashlib,json,os,stat,sys\n"
        "parts=[]\ntry:\n"
        f" for name,size,digest in {sources!r}:\n"
        "  p=os.path.join(os.environ['PLUGIN_ROOT'],'scripts',name)\n"
        "  fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))\n"
        "  with os.fdopen(fd,'rb') as f:\n"
        "   if not stat.S_ISREG(os.fstat(f.fileno()).st_mode): raise ValueError('Unsafe runtime')\n"
        "   b=f.read(size+1)\n"
        "  if len(b)!=size or hashlib.sha256(b).hexdigest()!=digest: raise ValueError('Runtime mismatch')\n"
        "  parts.append(b.decode())\n"
        "except Exception:\n"
        " try: event=json.load(sys.stdin).get('hook_event_name')\n"
        " except Exception: event='PreToolUse'\n"
        " reason='ACGM Session Guardian runtime integrity unavailable.'\n"
        " result={'continue':False,'stopReason':reason}\n"
        " if event=='PreToolUse': result={'hookSpecificOutput':{'hookEventName':event,'permissionDecision':'deny','permissionDecisionReason':reason}}\n"
        " if event=='UserPromptSubmit': result={'decision':'block','reason':reason}\n"
        " print(json.dumps(result));sys.exit(0)\n"
        "code=parts[0].rsplit('\\nif __name__ == \"__main__\":',1)[0]+'\\n'+parts[1]+'\\nhook_main()\\n'\n"
        "exec(compile(code,p,'exec'),{'__name__':'acgm_session_hooks','__file__':p})"
    )
    import shlex
    return "python3 -c " + shlex.quote(program)


def integrate():
    """Regenerate trusted Hook bytes in this checkout only; never install."""
    path = ROOT / "hooks/hooks.json"
    hooks = json.loads(path.read_text())["hooks"]
    content = (ROOT / "scripts/acgm_codex.py").read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    import re
    import shlex
    for groups in hooks.values():
        # Generated Guardian groups are regenerated, never accumulated.
        groups[:] = [g for g in groups if g["hooks"][0].get("statusMessage") != "ACGM 会话缓冲检查"]
        for group in groups:
            for handler in group["hooks"]:
                argv = shlex.split(handler["command"])
                program = re.sub(r"e=\d+", f"e={len(content)}", argv[2])
                program = re.sub(r"hexdigest\(\)=='[a-f0-9]{64}'", f"hexdigest()=='{digest}'", program)
                program = program.replace(" print('{}')", " print('{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"ACGM runtime integrity unavailable\"}}' if sys.argv[-1]=='pre-tool' else '{}')")
                handler["command"] = "python3 -c " + shlex.quote(program) + " hook " + argv[-1]
    hooks.setdefault("Interrupt", [{"hooks": [dict(hooks["Stop"][0]["hooks"][0],
                     command=hooks["Stop"][0]["hooks"][0]["command"].rsplit(" hook ",1)[0]+" hook interrupt")]}])
    hooks["Interrupt"][0]["hooks"][0]["timeout"] = 3
    command = integrated_guardian_command()
    for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "PreCompact"):
        hooks.setdefault(event, []).append({"hooks":[{"type":"command", "command":command,
                         "timeout":10, "statusMessage":"ACGM 会话缓冲检查"}]})
    path.write_text(json.dumps({"hooks":hooks}, ensure_ascii=False, indent=2)+"\n")


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
        f"if len(b)!={len(content)} or hashlib.sha256(b).hexdigest()!='{digest}': raise ValueError('ACGM runtime integrity mismatch')\n"
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
    parser.add_argument("destination", type=Path, nargs="?")
    parser.add_argument("--integrate", action="store_true")
    args = parser.parse_args()
    if args.integrate:
        integrate()
    elif args.destination:
        print(json.dumps(build(args.destination), indent=2))
    else:
        parser.error("specify --integrate or a trial destination")
