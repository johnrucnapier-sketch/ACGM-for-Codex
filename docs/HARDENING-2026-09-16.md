# ACGM for Codex：有限加固与 Session Guardian 集成审计

日期：2026-09-16。状态：**本地未提交、未发布的审核候选**。未 push、未改写历史、未升级用户已安装插件，未改生产项目或全局模型／权限设置。

说明：文中“未 commit／push／发布”描述验证完成时的审核状态。用户随后批准提交、推送与创建 Draft PR；后续交付状态以 Git 和 PR 为准，发布与安装仍需独立验收。

## 1. 当前真实基线与架构

- 仓库：`acgm-codex`；起点 `codex/session-guardian` / `1ff1bf37b62f857decd7b575912fc033323acaeb`，起始 working tree 干净，只有一个 worktree。
- 本轮分支：`codex/acgm-hardening-session-guardian`，直接保留现有四个 Guardian 提交。
- 只读 `git ls-remote` 验证远端 main 为 `e2a951956c0d61ae91cfef51712c0b585cee3a8b`，远端没有 `codex/session-guardian`。这只能证明该分支名不存在；本地四个提交不在已核对的 main 中，不声称遍历过所有远端对象。
- 本地 main 仍为 `06623a9`，比 origin/main 落后 10 个提交；没有强制同步或更改它。
- 当前正式版本／tag／已安装 ACGM：`0.3.0-rc.1`。本轮不分配新 release 版本。
- 核心是标准库 Python 单文件 `scripts/acgm_codex.py`：项目定位、治理状态／基线、HMAC 事件账本、少量危险操作 gate、固定检查、核验义务、doctor/report 和初始化／激活。
- 安装侧是已有 preflight/bootstrap/quickstart；核心 Hook 从 `PLUGIN_DATA/runtime/acgm_codex.py` 加载并校验精确长度和 SHA-256。技能承载语义判断与人工授权工作流。
- 仓库本身 doctor 为 `INSTALLED_NOT_BOOTSTRAPPED`，无 Constitution/scope/ADR/snapshot；没有为了开发而自动给它初始化治理。当前桌面任务在多仓库父目录，启动时 ACGM 明确未选项目；这不等于该仓库已被运行时机械 gate 覆盖。

## 2. Guardian 实现与实际使用状态

Git 核对的四个提交：`815f7e9`（reader/skill）、`67c7f48`（生命周期 Hooks）、`27bdfeb`（本地面板）、`1ff1bf3`（pending request/handoff）。

本机独立试用插件 `acgm-session-guardian@personal` 已启用，缓存版本 `0.1.0-local.1+codex.20260914070344`。安装运行文件 SHA-256 为 `6dd1153a1a2a373675a4f5a9bd3964d32e029f44f0c232b54e071deffb96c016`，与修改前仓库 reader+hooks 的构建字节一致。用户报告数天使用良好是用户验收信息；本轮独立验证安装字节和原生 synthetic 行为，没有把历史设计报告当作部署事实。

本机 CLI/Desktop rollout 版本为 `0.154.0-alpha.6.2`。本任务某次原生采样同时给出累计 451,392 token、最近响应上下文 85,809 token、有效窗口 258,400。Guardian 读取 `last_token_usage.total_tokens`／匹配 thread 的逐响应 usage，**不读取累计量作为 occupancy**；这是最近响应的官方估计，不是包含所有待输入附件的实时精确值。

本机 Astra 元数据报告 raw 默认窗口 272,000、max 872,000、effective 百分比 95。不能把 advertised maximum 当作本任务有效窗口。隔离 Harness 使用同一已缓存模型元数据与 500,000 配置，成功观察 475,000 有效窗口下的原有预算行为。

保留 35%／20%／10% 与原有 buffer 逻辑。500K raw、450K total compaction、40K handoff reserve、20K reaction margin 时，确认门仍约在 390K used（17.9% effective remaining）触发，410K 后不再允许继续一次。没有把临界门机械改成 10%。

自动 PreCompact 的拦截已在真实 Codex 引擎中发生，且该次运行只有一次固定响应请求，没有向 fixture 发起压缩生成。手动压缩仍是原有恢复出口。拦住压缩不保证剩余空间必然足够写完交接，必须先保存最小交接。

## 3. 正式集成方式与迁移边界

- 在**同一个 ACGM 插件**的 Hook 文件注册已有 Guardian reader/policy；不再需要未来安装第二个产品。依旧只有项目 `.acgm/session-guardian.json` 明确启用才工作。
- 复用原有源码，在内存中组合；读取两份文件后先校验 hash/长度，再执行，避免新增一份生成的 production runtime 副本。核心稳定 runtime 的路径和安装架构保留。
- `scripts/build_session_trial.py --integrate` 仅生成当前 checkout 的可信 Hook 字节；旧 trial builder 保留作历史复现。
- Guardian 状态、continue once、handoff、提示文字和预算原则保留。仅修复已复现的数据持久化／保留问题。
- 面板与 Hook 共用 `budget_metrics`；native audit 复用有界 reader，不引入新数据库或后台模型循环。
- 新增 `acgm-session audit` 是只读对账入口，不会改变 gate 或自动宣布验证完成。

**源代码集成已完成不等于已部署。**现有 companion 没被卸载，现有 ACGM 缓存没被替换。正式升级须选新版本，按既有精确安装计划发布 stable runtime，并由用户审核新 Hook 信任。启用集成版时不能同时保留生效的 companion；旧私有 pending archive 应保留作交接证据。未知安装冲突仍由现有安装器阻止，不自动合并或迁移。

## 4. Claude canary 经验逐项检查

| 检查题 | Codex 版实际结果／本轮处理 |
|---|---|
| requested != executed | PreToolUse 新增 request 记录；permission boundary 与 gate consumed 均不算 execution。无结果保持 unknown。 |
| executed != successful | 当前 Bash PostToolUse 原生输入是纯文本，确实没有退出码；不解析“成功”文字。native completion 对账才能给出成功／失败。 |
| failed/interrupted read 是否成为 evidence | 普通读取不是 gate evidence。固定非 shell 检查必须实际退出 0 才 arm/verify；请求已记录但检查未完成不产生 evidence。 |
| 无关成功读取 | `pwd`、其他目录 ls、SSH NAS/其他 host 的成功返回均不能代替固定检查。 |
| actual target | 原有目录 target 绑定保留；修复同目录不同 rm operand 可以复用 arm 的问题，增加完整命令 HMAC 绑定。native audit 同时匹配 session/turn/call/command 与可验证 target。 |
| remote host | 没有远端自动 evidence/arming。SSH 输出不当成本地 evidence，也不会跨 host 复用；不声称实现了通用 host 意图验证。 |
| empty/unreadable state | 原先 BROKEN/DRIFTED 提前返回以及异常 fail-open；现在 pre-tool 拒绝。显式 disabled、从未启用和多仓库未选项目仍不虚构已启用策略。 |
| root → subdir → deep subdir | 在隔离 Git 项目逐层运行 Hook，project_id 一致、危险命令均被拒绝；没有随 shell cwd 静默消失的复现。 |
| executable + argv | 没有凭 executable 名称授予“safe evidence”的通用 allowlist。date/date -s、uniq 两种输出形式、journalctl query/rotate、systemctl show/restart、nvcc version/compile 全部作为不同命令记录，均不能自动 arm。它们不是全部属于 ACGM 五个机械危险类别。 |
| compound shell | 对 `&`、`;`、`&&`、管道、`$(...)`、子 shell、`>`、`>>` 携带的受保护 destructive 命令逐项回归；补用已有 lexer 分段识别 argv，仍拒绝为复合／展开命令 arm。没有新增 shell AST。 |
| assistant 声称已验证 | 普通回复不能关闭义务。另修复 `resolve --status verified/resolved/unresolved` 曾一律关闭义务的问题：现在只是注记。显式 human_override/false_positive 仍作为人工处置保留，并不伪装执行验证。 |
| verification ordering | gate 请求、固定检查结果、同一 scope 的一次重试、后置固定检查顺序保留；失败检查、跨目标、跨 turn arm、不匹配 obligation 均有回归。zero exit 只完成机械检查，不证明业务 postcondition。 |
| deny 审计遗漏 | gate deny 原有记录保留；增加损坏策略拒绝与中断记录。原生 sandbox／审批未向 Hook 暴露的结论不伪造，保留 unknown 并与 native control 对照。 |

明确的限制：如果本地存在与远端同名路径且它位于 native 可写范围内，sandbox 不知道原本打算用 SSH；ACGM 当前也没有从自然语言推断 host 的通用机械策略。这需要 truth-first 的明确 target/host 约束与原生授权共同处理。不能把“SSH read 不会产生 gate evidence”夸大成“任意错误本地 cp 都会被阻止”。本轮没有为此复制 Claude 的 sandbox 或创建大型远端意图框架。

## 5. Native 与 ACGM 的职责边界

| 层 | 负责 | 不应声称 |
|---|---|---|
| Codex sandbox/network | 路径、进程／系统资源、网络执行边界 | 自动理解 NAS vs 本机的语义意图 |
| Codex approval / auto-review | 请求是否获准；平台权限决策 | 被批准就一定执行成功，或获得 ACGM 证据 |
| ACGM mechanical gate | 支持类别、明确 target/command、成功固定检查、一次重试、核验义务 | 完整 shell 安全解释器、SSH 主机策略、所有 mutation 的授权系统 |
| ACGM skills | 语义范围、用户授权、结果判读、决策／交接 | 不可绕过的操作系统边界 |
| ACGM ledger + native audit | 记录已观察事实，对可匹配原生 completion 做只读对账 | 未观察到的 permission verdict、全量历史、业务成功 |
| Guardian | context 生命周期、缓冲、一次继续、handoff、面板 | 零信息损失、绝对即时 occupancy、自动完成所有交接 |

[当前官方 Hook 文档](https://learn.chatgpt.com/docs/hooks)说明 PostToolUse 也会在非零退出后运行，并确认 PreCompact 的 `continue:false` 在压缩前停止。本轮用本机原生行为核对了这两点。权限职责参考[官方 approvals/security 文档](https://learn.chatgpt.com/docs/agent-approvals-security)，具体有效设置以当前任务与 Harness 原生结果为准。

当前桌面任务明确为 workspace-write、auto_review、受限网络、指定 writable roots；本轮第一次未升级的 GitHub 查询被网络限制拒绝，只读提升查询后成功。用户全局 config 没有显式 sandbox_mode/approval_policy/profile 或模型窗口配置，没有 `[profiles]` 条目或 `*.config.toml` profile 文件；工作区 trust 是父目录 trusted。不能把 trusted project 等同于 unrestricted execution。

本轮生成了该版本 app-server JSON schemas，并实际使用 native sandboxPolicy/approvalPolicy/approvalsReviewer 和 command/exec；CLI 的 `sandbox macos` 旧用法已不是当前接口。默认沙箱内启动另一个使用真实 CODEX_HOME 的 app-server 受到 SQLite 写入限制，未为读配置扩大真实环境权限。没有把这个失败称为 effective config/read 成功，也未为了 schema 差异修改任何用户设置。

## 6. 问题分级

| 级别 | 已验证问题 | 状态 |
|---|---|---|
| P0 | pre-tool 输入／内部错误、损坏／漂移治理状态、稳定 runtime 缺失可能 fail-open | 已修；pre-tool 输出明确 deny，已注册 Hook 被禁用／未受信任仍是平台覆盖边界 |
| P0 | 相同 parent/category 的另一个危险命令可花掉原 arm；复合 argv 识别不足 | 已修完整命令绑定并复用分段识别；不是通用 shell 证明 |
| P0 | Guardian malformed policy 可被当成未启用，自动压缩兜底消失 | 已修；明确未启用与读取失败分开 |
| P1 | PostToolUse 不能证明成功；审计缺少 requested/result/interrupt 区分 | 已修保守记录与 native 对账；未暴露的 native verdict 明确 unknown |
| P1 | resolve 的“verified”或“unresolved”标签会机械关闭义务 | 已修；人工 override 独立保留 |
| P1 | 第二条 pending request 的 list 原地变更可能不落盘；长／多请求只剩截断预览 | 已修 deepcopy dirty check 和完整私有 JSON archive；附件依赖不冒充已备份 |
| P2 | 面板遗漏 native `exec` source | 小修加入 exec，仍排除 subagent；真实 CLI fixture 显示 1 个任务 |
| P2 | native Bash 纯文本无 exit code；部分拒绝没有 completion | 当前平台可观察性限制；不猜测、不 fail-open 成 success |
| P2 | damage/drift fail-closed 会阻止该项目内 ordinary tools，需要明确修复／回滚 | 有意取舍，保留 native/外部 doctor 路径；未偷偷放宽权限 |
| P2 | 单次大输入／长 generation 可能越过缓冲；过晚 PreCompact 停止后仍须新会话恢复 | 原有边界，保留 UX，不承诺所有 handoff 必然有足够空间 |
| P3 | 核心单文件较大、多个发布/历史安装路径、有限 shell 启发式 | 记录未来整理，不进行全面重构 |

## 7. 实际修改与 production 增量理由

| 文件／模块 | 解决的已验证问题 |
|---|---|
| acgm_codex.py | fail-open、arm 可跨完整命令复用、复合 argv 漏判、执行记录混淆、声称 verified 关闭义务；同一 target 提取供只读对账复用 |
| build_session_trial.py | 将已试用 Guardian 注册到现有插件，绑定精确源码，不生成另一套源码副本；完整性检查不依赖可被 Python 优化关闭的 assert |
| session_guardian.py | Hook/面板预算重复；原生纯文本 Hook 不能审计成功，因此复用 reader 的 observer 做 completion 对账 |
| session_hooks.py | 无效策略静默停用、嵌套请求变更漏存、请求截断丢失；完整请求以本地私有文件保存 |
| session_dashboard.py | 复用预算函数并显示本机实际存在的 exec 来源任务 |

无 production 新模块、无数据库、无动态 DI、无替代 native sandbox/approval。生成 Hook 和 manifest 的变化是精确字节信任更新，未执行安装。

## 8. Unit 与真实 Harness

基线 release_check：**211 tests，全部通过**，plugin/skills/manifest 合约通过。首阶段最终 release_check：**228 tests，全部通过**，plugin、六个 skills 与 manifest 合约全部通过；最后一次 suite 的原始结果保存在 `.acgm/hardening/final-release-check.json`。

`tests/native_harness.py` 使用真实 `codex exec` 与 `codex app-server`，临时 CODEX_HOME、临时 Git 项目、仅 loopback 的固定 Responses SSE。模型调用由确定性 fixture 替代，不调用 OpenAI 模型或真实服务器。Hook 信任跳过仅限这次已审阅的隔离 fixture，不写用户 trust。核心 runtime 使用生成命令和同样字节校验；这是原生引擎+真实 Hook 执行测试，不是安装到当前桌面的新版插件验收。

| 场景 | Native decision / execution | ACGM / audit |
|---|---|---|
| local safe read / local mutation | 实际运行，exit 0 | request 与原生 completion 匹配，success |
| execution failure | exit 7 / failed | Hook text 为 unknown，native audit 为 execution-failed |
| read-only sandbox block | 禁止写入，文件不存在 | 无成功 completion；request 未对账，不能称已 mutation |
| approval policy deny | require_escalated 被拒，文件不存在 | 不伪造许可或成功 |
| 原生 approval decline | 真正 requestApproval → decline，native declined，文件不存在 | 独立 control 未加载 ACGM；不声称该行证明插件拦截 |
| 原生 approval accept | requestApproval → accept，完成 exit 0，文件存在 | 同上；证明 native approval 与 actual execution 分离 |
| compound destructive | PreToolUse 拒绝；无 destructive execution | gate-denied 已记录；无 native completion |
| low / 35% / 20% | 保持正常生成／执行 | 原有 warning/suggestion 路径通过 |
| critical | 第二个工具被原生 Hook 拒绝 | 显示约 17.7% remaining／58,980 room，符合原 buffer |
| continue once | 原生 resume 中放行一轮 | 下一普通 prompt 被挡，fixture response 请求数 0 |
| handoff | 同一旧 session 的真实 handoff prompt 后工具可执行 | 原有 handoff grant 保留；pending archive 单测覆盖完整原文 |
| PreCompact auto | 原生取消，CLI exit 1；只发出第一次 fixture response | PreCompact 一次，Interrupt 一次；无压缩生成请求 |
| new session | 新 session 正常执行 | 不继承旧 allowed/handoff/blocked 状态 |
| interrupted running process | command/exec 的 sleep 已输出 started，再原生 terminate；exit 137 | 单独控制不代表工具 Hook 覆盖；不得写成功 |
| dashboard | 三次本地 HTTP status，额外模型请求 0 | native exec 来源小修后显示同一任务；旧样本如实 UNKNOWN |

root/nested、remote evidence 混淆、argv pairs、全部 compound 运算符、未完成 evidence、核验排序、错误 state、跨目标、并发一次 arm、pending request 保存，以及事件对账由回归测试覆盖。它们不是在真实 NAS、服务器或生产项目执行。固定模型响应不能验证真实模型是否遵从提醒文案，也不能替代用户对 Desktop 视觉呈现和语义交接内容的验收。

原生综合测试共 18 行场景，观察 SessionStart 15、UserPromptSubmit 15、PreToolUse 18、PostToolUse 15、Stop 13、PreCompact 1、Interrupt 1。approval controls 独立于此 Hook 计数。面板最初没有显示 exec source，修复后另做真实 retained CLI fixture 的三次 HTTP 检查，1/1/1 个任务，未启动模型。

证据存放在本仓库 gitignored `.acgm/hardening/`：`native-results.json`、`dashboard-native.json`、`interrupt-native.json`、`baseline-release-check.json` 与最终 release check。原始测试文件只含 synthetic 数据；公开报告不包含私有 HMAC key、用户 prompt 或配置凭据。

## 9. 首阶段 LOC、文件、模块（后续总量见第 13 节）

口径：物理行（包含注释与空行）；production 为 scripts、bin 与 dashboard HTML 的源码，tests 为 tests 下 Python。生成 hooks JSON、manifest、文档不计入 source LOC，单独保留 diff。起点为本轮 Git HEAD `1ff1bf3`，包括已经存在的 Guardian，不能把原有模块冒充本轮新增。

| 项目 | 修改前 | 修改后 | 净变化 |
|---|---:|---:|---:|
| production LOC | 9,720 | 9,942 | +222 |
| test LOC | 7,292 | 7,697 | +405 |
| production source files | 14 | 14 | 0 |
| production Python modules | 11 | 11 | 0 |
| test source files/modules | 10 | 12 | +2 |

最初进度中的 9,699 是 scripts/bin 口径；此表补入前后均存在的 21 行 dashboard HTML，形成完整 source 口径，不改变净增量。

## 10. 重复安全语义核对

read-only evidence 仍只有固定非 shell check；不新增通用 executable allowlist。destructive 分类仍在核心，constitution 写保护是不同约束；本轮只复用已有 lexer。target 提取由核心同一函数复用于 audit。execution state 判读共用 `_execution_outcome`。evidence 仍用既有账本/固定检查。context lifecycle、Hook/panel budget 合一；native audit 不复制 rollout reader。没有引入第二套 session governor。

CLI status 的 window-only／显式 compact-limit 展示与 lifecycle buffer 是既有不同视图，文档保留其区别；没有为减少 LOC 删安全测试。hash wrapper 的核心 stable-runtime 与 Guardian 源文件装载是两个现有部署约束下的小 adapter，不是新的 plugin framework。

## 11. Future simplification / 尚待确认

1. 原生若提供完整稳定的 PostToolUse execution/permission envelope，再考虑移除或缩小内部 rollout fallback；未验证版本保持 UNKNOWN。
2. 清理 trial-only builder／文档须等 companion 完成正式迁移，不能本轮删除恢复路径或旧状态。
3. 核心单文件的安装逻辑可未来单独讨论；本轮不拆成 class hierarchy。
4. 对完整 shell 语法、任意远端 host 意图、MCP 非 Bash mutation 的策略覆盖要另立明确范围，不把本次有限 gate 加固宣传为全面沙箱。
5. 新插件安装、用户信任、真实 Desktop 新进程加载与一次正常业务 handoff/新 session readback，是发布前独立验收；本轮没有打断运行中的桌面环境去做升级。
6. approval/sandbox 缺失的原生结果需要未来更完整 native telemetry；当前审计选择 unknown，不能用文字推断补齐。

## 12. 是否建议推送 GitHub

建议用户审核后将此分支作为 **draft PR 候选** 推送；不建议直接发 release。先审查 fail-closed 带来的操作体验、完整 pending archive 的保留规则、native audit 的覆盖边界，以及 companion → 集成模块的迁移计划。版本更新、安装／trust 验收和公开发布分开进行。

本轮未 commit、未 push、未发布。回滚当前代码只需针对本轮 diff 审阅恢复；原 Guardian 分支和起点 commit 保留。已安装的 ACGM、companion、全局配置和生产项目均未由本轮替换，因此没有需要用户执行的线上回滚。


## 13. 后续有限策略层与最终收尾（2026-09-16）

用户在设计讨论后批准继续薄策略层实现；不包含自动 push、release 或升级已安装插件。
详细边界见 [WORKFLOW-PROFILES.md](WORKFLOW-PROFILES.md)。复用了核心 runtime、既有
治理基线和事件账本，没有新生产模块、依赖、数据库或三套 Gate。

### 实际增量与复查结果

- Light / Standard / Strict 只调整工作流要求；现有机械 Gate、权限边界与 evidence 约束不降级。
- 可选项目能力/档位决定受已有 activation baseline 保护；缺省 Standard。
- 风险底线、用户提高要求和能力建议取最高值；服务与破坏性动作至少 Strict。
- 同 session、target/category 的连续固定检查失败可锁定 Strict；普通命令失败、unknown、
  approval deny 不触发。新 session 独立，操作临时 Strict 不锁定整个 session。
- Guardian 开关和阈值未随 profile 改动；不宣称有通用模型能力探测或 remote 意图分类器。
- 复查发现开发安装器的固定 allowlist 漏掉 Guardian runtime、面板与 handoff 技能。
  临时快照复现了六个关键文件缺失；以 13 行清单补充修复，并执行复制后的 hash-bound
  Guardian loader 验证。该开发 helper 仍不是正式版迁移路径，不替代 Git 发布包验收。

### 最终原生隔离验证

当前 CLI `0.154.0-alpha.6.2`，临时 Git 项目、临时 CODEX_HOME、仅回环的固定 Responses。
23 个场景、21 项显式验收条件全部通过。测试现在会在验收失败时非零退出，不能只凭
Codex turn exit 0 将被拒绝操作判为执行成功。

| 新增/交叉场景 | 原生结果与 ACGM 证据 |
|---|---|
| Light safe read | 模型输入收到 Light 指引，读取完成 |
| Light destructive | 无 destructive completion，Gate 拒绝 |
| 两次固定检查失败 | 两次 CLI exit 3，一条 policy-escalated |
| 同会话 resume | 新的 SessionStart 提供 Strict；历史 Light 文本仍保留为历史 |
| 新会话 | 提供 Light，不继承上一会话升级 |
| Light + Guardian | 继续一次、下一请求阻断、交接、自动压缩拦截与新会话独立均通过 |
| 面板 | 三次 HTTP 查询均有任务，额外 fixture 模型请求为零 |

原生 Hook 计数：SessionStart 20、UserPromptSubmit 20、PreToolUse 25、PostToolUse 20、
Stop 18、PreCompact 1、Interrupt 1。独立 approval accept/decline 控制没有 ACGM Hook，
不能计作联合覆盖。原始证据在 gitignored `.acgm/policy-review/native-results.json`。
固定模型不能证明真实模型对提示的遵从或节省 token；安装、Desktop 新进程加载、用户
Hook 信任以及真实业务交接体验仍是独立验收项。

最终完整检查：**238 tests 全部通过**（140.358 秒），plugin、六个 skills 和 manifest 合约
全部通过；原始结果为 `.acgm/policy-review/final-release-check.json`。文档收尾后另行
复核 manifest 与 whitespace。只读远端核对：main 为 `e2a951956c0d61ae91cfef51712c0b585cee3a8b`，
它仍是当前 HEAD 的祖先，远端尚无本候选分支；没有改写或发布远端状态。

### 最终规模与发布判断

| 项目 | 原始起点 | 当前候选 | 净变化 |
|---|---:|---:|---:|
| production LOC | 9,720 | 10,104 | +384 |
| test LOC | 7,292 | 7,908 | +616 |
| production source files | 14 | 14 | 0 |
| production Python modules | 11 | 11 | 0 |
| test source files/modules | 10 | 13 | +3 |

生产增量拆分：原加固/Guardian 集成 +222，薄 profile resolver +149，开发快照遗漏修复 +13。
完整原生用例脚本、回归和复制快照验证属于测试代码，不计入 production。

建议作为 draft PR 审阅候选，不直接发 release。源码/包检查与原生隔离测试通过仍不等于
已安装版本生效。用户已安装插件、companion、全局权限/模型配置和生产项目保持原状；
本轮仍未 commit、push 或发布。具体 PR 文案可在 `.acgm/policy-review/PR-DRAFT.md` 审阅。
