# ACGM for Codex

**让长周期 Agent 编码不再悄悄漂移。**

ACGM for Codex 是 ACGM（Agent Coding Governance Methodology）的独立 Codex
适配产品。它把长期项目中的实现漂移、认知漂移、结构位置漂移和范围漂移，变成可见的
项目状态、可机械判断的窄护栏，以及一个只保留脱敏结果的本机 Event Ledger。

[English](README.en.md)

> **当前状态：`0.2.0-rc.1`。** 这是公开预览候选版，不是稳定发行版。自动测试可以证明
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
- 一次授权 quickstart：自动生成版本化治理预设、激活项目并验证本地 postcondition；
- `acgm-codex quickstart / init / activate / doctor / report / export-case / resolve / gate / version`。

详细的机械保证与已知缺口见 [ARCHITECTURE.md](ARCHITECTURE.md) 和
[EVIDENCE.md](EVIDENCE.md)。

当前命令识别器只覆盖 hard reset、forced clean、forced branch delete、force push 和
recursive forced delete 的已识别写法。被识别为高风险、但包含 shell 展开、复合执行或
模糊 target 的命令会被拒绝且不能 arm；未识别的 alias、wrapper、间接写入和其他工具路径
仍不在完整保证内。

## 从 GitHub 安装公开预览版

当前候选版通过 Codex 官方 Git marketplace 安装，不会覆盖 Claude Code 版 ACGM。用户只需
明确要求 Agent“在这个准确项目里安装并启用官方 ACGM，采用推荐默认值”。这一句话就是对
精确 `standard-v1` 计划的一次授权，不需要再逐项批准或手写治理文件。

Agent 自动克隆准确 tag，并运行：

```bash
ACGM_SOURCE="$(mktemp -d)/ACGM-for-Codex"
git clone --branch v0.2.0-rc.1 --depth 1 \
  https://github.com/johnrucnapier-sketch/ACGM-for-Codex.git "$ACGM_SOURCE"
python3 "$ACGM_SOURCE/scripts/quickstart.py" \
  --project /准确项目的绝对路径 --dry-run --json
python3 "$ACGM_SOURCE/scripts/quickstart.py" --project /准确项目的绝对路径 \
  --plan-digest <dry-run返回的digest> --authorize --json
```

工具源码应克隆到目标项目之外的临时目录，避免在被治理仓库中留下嵌套 clone。

可以直接对 Agent 说：

> 从官方 GitHub 仓库安装 ACGM for Codex，在当前准确项目采用推荐默认值；自动完成下载、
> 安装、治理文件生成、激活和验证。不要覆盖已有项目策略或迁移旧安装。

只有贴 URL、没有要求安装时仍然只代表允许下载与只读检查。Quickstart 的 dry-run 是机器
校验，不是让用户再审一遍：digest 会绑定官方 source/tag、固定安装命令、有效 Codex profile
目标的不可逆身份、准确 Git root、Git identity、既有文件 hash 和全部拟写入字节；apply 前
任一事实变化都会使授权失效。

全新安装只调用两条固定官方命令：`codex plugin marketplace add
johnrucnapier-sketch/ACGM-for-Codex --ref v0.2.0-rc.1 --json` 与 `codex plugin
add acgm-codex@acgm-codex --json`。唯一的插件自动升级例外，是一个已启用、user scope、
来源/ref/policy/marketplace snapshot/package bytes/唯一 cache 全部验证通过的官方
`0.1.0-rc.2`、`0.1.0-rc.3` 或 `0.1.0-rc.4`；此时 digest 会明确绑定
`marketplace remove -> exact-ref marketplace add -> plugin add` 三步。之后再次独立核对
目标版本和 cache package bytes；外部命令中途失败会报告 partial/recheck，不会声称已回滚。
插件安装成功后若项目 root 又发生变化，组合结果会明确返回
`PROJECT_RECHECK_REQUIRED` 与 `partial=true`，不会抛出无人可读的 traceback。

Quickstart 随后自动生成缺失的 Constitution、scope、adoption decision 和 snapshot，保留
已有 `AGENTS.md` 和有效治理策略，只替换旧 ACGM `init` 生成的 byte-identical 占位模板，
并自动 activate 与运行 doctor。Quickstart 要求传入准确 Git root；传入父 workspace 会在
写入前停止，不猜测子仓，也绝不把治理文件写到空父仓。只有 runtime Hook 的项目解析器可以
在 unborn 父仓下自动选择唯一子仓，而且要求 `.git` 之外的全部条目都是已验证直接子仓；
普通 untracked/ignored 父文件会使这种 runtime-only 选择停止。

Codex 自己的 Hook 信任是唯一必需的 ACGM 专属安装后确认。下一个正常 task 启动时，如果待审核
列表里只有刚刚校验过的本版本 ACGM Hooks，可以使用当前 Codex 提供的 **Trust all and
continue**，一次确认整组定义；如果混有其他未知 Hook，则必须分别审核，不能为了省步骤而
一并信任。信任后第一次真实 ACGM Hook 调用会自动记录当前 activation heartbeat，不再要求
额外开第二个“验证任务”。环境自身仍可能显示网络、文件或命令权限提示；ACGM 不绕过
Codex 或操作系统的安全边界。

旧 `acgm-codex@personal`、重复插件、其他 scope/source/ref、未知版本或更高版本全部失败关闭；
上面列出的唯一官方 RC2/RC3/RC4 是自动插件升级例外。Quickstart 永远不会吸收、重置或搬运
私有 `PLUGIN_DATA` / Event Ledger。未知策略与其他冲突仍在修改前停止，详见
[INSTALL.md](INSTALL.md)。

公共安装不会给 shell `PATH` 增加 wrapper；skill 会从已安装插件根目录解析 launcher。
`scripts/install_local.py` 仅供维护者在隔离 HOME 中测试旧 personal 开发路径。

当前候选版仅支持 macOS/Linux 与 Python 3.10+。Windows 明确 BLOCKED：当前 runtime 仍依赖
POSIX `fcntl` 锁；Windows Codex app 支持插件不等于本 runtime 已可移植或通过 E2E。

## 在项目中启用

推荐让 Codex 执行：

```text
Use $governance-bootstrap to quickstart ACGM in this repository with recommended defaults.
```

skill 会自动运行 digest-bound quickstart。也可以直接运行：

```bash
acgm-codex quickstart plan /准确项目绝对路径 --json
acgm-codex quickstart apply /准确项目绝对路径 --plan-digest <digest> --authorize --json
acgm-codex quickstart status /准确项目绝对路径 --json
```

`standard-v1` 是版本化安全预设。用户对 quickstart 的一次授权即表示采用这些准确字节，
不要求亲手输入 Constitution。已有有效策略始终保留；只有版本号变化且既有 baseline
仍完全匹配、而且来源是明确兼容的 RC2/RC3/RC4 project adapter 时，quickstart 才会在同一次
授权中安全升级 adapter state；未知或更高版本不会被自动降级。健康、已手工 activate 的项目
也可以在保留 activation id 的前提下采用缺失的标准 decision/snapshot。其他 active drift、
未知 receipt、并发 Git/index 变化、未知占位符、symlink 或非普通文件会在自动吸收前停止。
Custom policy 仍可使用兼容的 `init` / `activate` 手动路径。

`apply` 完成后项目立即是 `GOVERNED`；若尚无真实 Hook heartbeat，则状态是
`AWAITING_PLATFORM_HOOK_ACCEPTANCE`。这表示本地设置成功、平台自动机制尚待一次信任，
不是治理文件失败。第一次真实 Hook 运行后，`quickstart status` 或 strict doctor 会报告完成。
如果已经出现 heartbeat 后又发生 Hook runtime error，则明确报告
`HOOK_RUNTIME_REPAIR_REQUIRED`；本机安装或账本损坏则报告
`LOCAL_RUNTIME_REPAIR_REQUIRED`，不会伪装成“只差首次信任”。

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
