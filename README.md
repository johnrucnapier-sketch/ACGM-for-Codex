# ACGM for Codex

**让长周期 Agent 编码不再悄悄漂移。**

ACGM for Codex 是 ACGM（Agent Coding Governance Methodology）的独立 Codex
适配产品。它把长期项目中的实现漂移、认知漂移、结构位置漂移和范围漂移，变成可见的
项目状态、可机械判断的窄护栏，以及一个只保留脱敏结果的本机 Event Ledger。

[English](README.en.md)

> **当前状态：`0.1.0-rc.4`。** 这是公开预览候选版，不是稳定发行版。自动测试可以证明
> 包结构和运行时行为；只有完成全新 Codex task 中的 Hook 信任与真实工具调用 E2E 后，
> 才能声称自动机制已在当前 Codex 版本上运行。

它不会覆盖或替代原有的
[ACGM for Claude Code](https://github.com/johnrucnapier-sketch/Agent-Coding-Governance-Methodology)。
两个产品使用不同插件身份、安装目录、运行协议和本机数据命名空间。

## 它解决什么

单纯把规则写进文档，并不能保证新 task、compact 后的 task、subagent 或新 worktree 会继续
执行规则。ACGM for Codex 因而把治理拆成三层：

| 层 | 作用 | 保证边界 |
|---|---|---|
| Methodology | 定义 Constitution、Truth-first、ADR、snapshot、scope 与验证义务 | 规范，不是自动执行 |
| Skills | 在初始化、恢复、高风险变更和报告时给 Codex 可复用流程 | 可显式调用或由模型选择 |
| Hooks + runtime | 启动时检查状态、拦截可机械判断的窄风险、追踪验证义务并写本机账本 | 确定性护栏，但不是不可绕过的安全边界 |

Codex 官方目前说明：`PreToolUse` 对 `unified_exec` 的拦截并不完整，也不覆盖所有工具。
个人插件还可以被禁用，Hook 定义也必须由用户审查并信任。因此本项目不会把“安装过”写成
“所有操作都被强制治理”。

## 当前能力

- 五态项目健康模型：`INSTALLED_NOT_BOOTSTRAPPED`、`PARTIALLY_GOVERNED`、
  `GOVERNED`、`DRIFTED`、`BROKEN`；
- `SessionStart` 和 `SubagentStart` 自动注入当前项目状态与 grounding 提示；
- `PreToolUse` 在已识别的写入路径上保护由人所有的 Constitution，并对一组窄匹配破坏性命令执行 evidence gate；
- `PermissionRequest` 只记一条脱敏边界观察，不批准、不拒绝，也不替用户形成治理决定；
- evidence gate 不把 Codex Bash `PostToolUse.tool_response` 的纯文本当成成功凭据；
  `gate arm` / `gate verify` 由 runtime 直接运行固定参数、无 shell 的只读检查，并只在真实
  exit code 为零时改变 gate 或义务状态；检查输出仍须人工或 Agent 解释后才能声称语义验证；
- `Stop` 对尚未出现匹配检查的动作最多续跑一次，避免无限循环；
- `PreCompact` 只保存脱敏 heartbeat，不保存项目 snapshot 或压缩内容；compact 后由
  `SessionStart` 根据当前项目文件重新 grounding；
- 本机、append-only、source-minimized Event Ledger；
- 四个 Codex skills：`governance-bootstrap`、`session-grounding`、`truth-first`、
  `activity-report`；
- `acgm-codex init / activate / doctor / report / export-case / resolve / gate / version`。

详细的机械保证与已知缺口见 [ARCHITECTURE.md](ARCHITECTURE.md) 和
[EVIDENCE.md](EVIDENCE.md)。

当前命令识别器只覆盖 hard reset、forced clean、forced branch delete、force push 和
recursive forced delete 的已识别写法。被识别为高风险、但包含 shell 展开、复合执行或
模糊 target 的命令会被拒绝且不能 arm；未识别的 alias、wrapper、间接写入和其他工具路径
仍不在完整保证内。

## 从 GitHub 安装公开预览版

当前候选版通过 Codex 官方 Git marketplace 安装，不会覆盖 Claude Code 版 ACGM。
只提供仓库名或 URL 仅授权下载与只读检查，不等于授权修改用户配置。先克隆准确 tag：

```bash
git clone --branch v0.1.0-rc.4 --depth 1 \
  https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git
cd ACGM-for-Codex
python3 scripts/preflight.py --json
python3 scripts/bootstrap.py --dry-run --json
```

Agent 展示准确计划并得到明确安装授权后，才可执行：

```bash
python3 scripts/bootstrap.py --authorize-install --json
```

如果希望“一句话交给 Agent”，可以把授权写完整：

> 只从 `johnrucnapier-sketch/ACGM-for-Codex` 克隆 `v0.1.0-rc.4`，读取
> `AGENTS.md` 与 `INSTALL.md`，运行 preflight 和 dry-run；如果源码、manifest、现有安装
> 状态与文档中的两个固定 Codex 命令完全一致，我明确授权执行这两个用户级插件配置命令。
> 安装验证后停在 Hook trust，不得迁移旧 personal 版或读取 Event Ledger。

这段完整指令允许 Agent 连续下载、检查、安装和验证；只贴 URL 仍然只代表允许检查。

Bootstrap 只调用固定的官方命令：`codex plugin marketplace add
johnrucnapier-sketch/ACGM-for-Codex --ref v0.1.0-rc.4 --json` 与 `codex plugin
add acgm-codex@acgm-codex --json`。之后独立核对 marketplace source/ref、插件
name/version/enabled 和 cache package bytes；外部命令中途失败会报告 partial state，不会
声称已回滚。

随后必须：

1. 新开一个 discovery task，让新插件被加载；
2. 在 Codex 中打开 `/hooks`，审查并信任 ACGM 当前 Hook 定义；
3. 再新开一个 verification task，让已信任的 `SessionStart` 从任务开始运行；
4. 验证 heartbeat 后，在目标项目调用 `$governance-bootstrap`。

旧 task 不保证重新加载刚安装的 skills 和 Hooks。Hook 内容变化后，Codex 会按新 hash 要求
重新审查，这不是安装失败。

旧 `acgm-codex@personal`、重复插件、其他 scope/source/ref 或版本冲突全部失败关闭；
bootstrap 不会自动卸载、覆盖、吸收或搬运私有 `PLUGIN_DATA` / Event Ledger。安装、Hook
信任、新 task heartbeat 和项目 bootstrap 是四个不同状态，详见 [INSTALL.md](INSTALL.md)。

公共安装不会给 shell `PATH` 增加 wrapper；skill 会从已安装插件根目录解析 launcher。
`scripts/install_local.py` 仅供维护者在隔离 HOME 中测试旧 personal 开发路径。

RC4 仅支持 macOS/Linux 与 Python 3.10+。Windows 明确 BLOCKED：当前 runtime 仍依赖
POSIX `fcntl` 锁；Windows Codex app 支持插件不等于本 runtime 已可移植或通过 E2E。

## 在项目中启用

推荐让 Codex 执行：

```text
Use $governance-bootstrap to initialize ACGM governance in this repository.
```

也可以手动运行：

```bash
acgm-codex init .
acgm-codex doctor .
```

`init` 幂等且不会覆盖已有 `CONSTITUTION.md` 或 `AGENTS.md`。Constitution 由用户所有：
Codex 可以起草提案，但初始化后不能用自动化工具替用户写入该文件。用户亲自完成
Constitution，并完成非占位 scope、至少一条 decision 和一个当前 snapshot 后，再运行：

```bash
acgm-codex activate .
acgm-codex doctor .
```

`activate` 会为上述文件以及 decision/snapshot 目录中的非隐藏文件建立内容 baseline。
内容增删改会报告 `DRIFTED`。激活也会重置 heartbeat 验收时间，因此应新开 Codex task，
在 `/hooks` 确认当前定义已信任并让 `SessionStart` 运行，然后再执行
`acgm-codex doctor . --strict`。在这个新 heartbeat 出现前，strict 失败表示自动机制尚待验收，
不表示治理内容本身无效。

安装但未初始化的项目会持续被报告为 `INSTALLED_NOT_BOOTSTRAPPED`；缺资产不会被悄悄
改写成 `GOVERNED`。

## 查看它发现了什么

```bash
acgm-codex doctor . --json
acgm-codex report --project current --limit 20
```

也可以调用：

```text
Use $activity-report to explain what ACGM detected in this project.
```

Activity 只说明机制运行过；只有存在明确触发、动作影响和后续验证时，事件才可以称为一次
interception。`export-case` 只生成本地脱敏预览：它拒绝覆盖已有文件以及项目治理/运行时
状态路径，分享前仍必须逐行人工复核。

## 隐私

Hook 输入只在内存中处理。Ledger 不保存 prompt、transcript、源码、完整命令、文件路径、
模型/服务商名、remote URL、凭据或可重建的技术指纹。项目、session 和 tool 只以本机盐化
opaque ID 存储；目标也只保存 HMAC ID；同一 HMAC target 才能关联 gate、检查和义务；
没有自动上传。

当前 RC 尚未自动轮转 Event Ledger；事件查找会随本机账本增长而线性增加。大型长期账本的
归档与新审计 epoch 必须人工规划，不能只移动账本却遗失对应 HMAC key。

安装 Hook 首次运行时会把官方 `PLUGIN_DATA` 位置写入权限为 `0600` 的本机 locator，供
standalone CLI 与 Hook 共用同一本账本；locator 本身包含这个数据目录路径，不属于 Event
Ledger 事件内容。若账本仍在但本机 HMAC key 丢失，runtime 会拒绝静默生成新 key；只有把
旧账本与 key 一起保留/恢复，或把两者一起移走并明确开始新审计 epoch，才能继续。
Hook 负责初始化账本并加固权限；standalone `doctor` / `report` 只读解析已有 locator、key
和账本，不会为了检查状态而创建目录、执行 `chmod` 或打开可写 lock，因此可在只允许读取
plugin data 的受管 Codex 沙箱中运行。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
python3 scripts/release_check.py
```

真实平台验收按 [tests/manual/CODEX_E2E.md](tests/manual/CODEX_E2E.md) 执行。

## License

机械代码使用 MIT；方法论文档和 skill 正文使用 CC-BY-4.0。详见
[LICENSING.md](LICENSING.md)。
