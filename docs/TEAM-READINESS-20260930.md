# Astra 适配与队友安装复核 — 2026-09-30

结论：继续使用已发布的 **v0.4.0-rc.2**，本次只更新文档，不发行新 runtime。
RC2 于 2026-09-28 发布，main 当时的提交为
`6d35f2f11e4a517e9f7214b295704cbdaf6c8442`；并非因额度耗尽而未完成。
本次文档提交不会移动该标签，也不要求现有 RC2 用户重新安装或重新信任 Hooks。

## 面向 Astra 的取舍

本产品当前面向运行于 Codex 的 Astra 系列顶尖模型。普通短任务不预先要求
完整恢复、doctor 或 Gate 卡片；只恢复当前任务需要的事实，沿用已有有效授权。
风险与真实失败决定何时需要检查，模型能力不是降低危险操作底线的依据。
长期项目保留重要决策、未完成验证和交接；Guardian 独立按需启用。

不新增弱模型辅助、模型能力数据库、自动模型识别或三套工作流。
现有 Light / Standard / Strict 配置接口只保留兼容，不为旧配置擅自降级。
默认健康项目入口已经安静运行，不需要先跑 policy 才能开始普通工作。
这不是零开销：技能目录、完整性检查和本机账本仍有成本。

## 参考 Claude Code 今天的更新

对照来源：[v0.9.6-rc.3](https://github.com/johnrucnapier-sketch/ACGM-for-Claude-Code/releases/tag/v0.9.6-rc.3)，
提交 `f3bc7a852dd35746df14f9d606f1fcd06af9a84e`。
比较了发布说明、grounding/ledger 技能、诊断入口和 Gate/观测代码。

| Claude 变化 | Codex 现状与决定 |
|---|---|
| 开场不再默认完整 doctor，复用授权 | 已由 session-grounding 和安静 SessionStart 实现，保留 |
| 拒绝原因附下一步；不支持的目标不诱导重复填表 | 现有 Gate 已区分不可 arm 的复合/模糊目标与可执行的固定检查；RC2 还修复了 doctor 自锁。保留，有真实误导案例再定点修复 |
| 私有、有限保留、尽力写入的观测日志 | Codex 已有脱敏 Event Ledger 和 report；不再增加第二套日志或每次 Hook 的额外 Python 进程 |
| 只读命令 inspector | 暂不复制。Codex Gate 检查依赖当前事件、授权重试和账本；直接重放 Hook 可能产生事件，不能冒充纯只读诊断 |
| 精确 hash 绑定的远程工具登记 | 暂不移植。两者远程识别与证据模型不同，不能将 Claude 的登记规则当作 Codex 已有能力；待真实需求证明收益 |
| ledger 模板路径修复 | Codex 已使用技能目录下 assets 的相对链接，无同类缺口 |
| 引用提醒不覆盖有效运行证据 | 保留证据原则；Codex 无需复制该引用启发式检查 |

两种日志不完全等价：Claude 的新日志是可丢失的诊断观测，Codex 账本还参与
重试许可与验证义务。不能照搬“日志失败不影响决定”或按天删除，否则可能丢失
未完成义务。若以后优化账本读取/存储，应先测量真实开销并设计义务保留，
不在此次队友安装前增加未经验证的生命周期逻辑。

## 队友安装

支持 macOS / Linux、Python 3.10+。Windows 当前被明确阻止；本次没有新增支持。
队友在 Codex 打开自己的**准确项目文件夹**，将下面文字交给 Agent：

> 请从 https://github.com/johnrucnapier-sketch/ACGM-for-Codex 的
> v0.4.0-rc.2 标签，在当前准确 Git 项目安装并启用 ACGM for Codex，采用推荐默认值。
> 按该版本 INSTALL.md 自动完成校验、安装、项目初始化、激活和验证。
> 保留已有项目策略、原生 sandbox 和 approval；不要复制别人的全局配置或本机账本。

Agent 使用该标签的 [INSTALL.md](https://github.com/johnrucnapier-sketch/ACGM-for-Codex/blob/v0.4.0-rc.2/INSTALL.md)
执行一次授权流程。安装后完全退出并重开 Codex，在设置中审阅并信任准确的 ACGM
Hooks；CLI 可使用其支持的 `/hooks`。插件安装不等于 Hook 自动获信任，见
[官方 Hooks 文档](https://learn.chatgpt.com/docs/hooks)。

随后正常继续项目任务，由第一次实际 Hook 记录完成运行验收。Agent 应使用
当前安装插件的绝对 CLI 路径检查 doctor / quickstart status，避免旧全局 wrapper。
若仍缺心跳，报告缺什么，不伪造事件或为了“健康”重新激活项目。
普通短任务不必开启 Guardian；长期任务可单独选择，不因模型名称强制开启。

## 本次验证及边界

- 完整发布检查：253 项源码测试与包、6 个技能、manifest 契约通过。
- 原生 Codex 0.158.0-alpha.2.1 Harness：28 场景、27 条断言通过，覆盖安静入口、
  升级后首条命令、受限诊断、风险拒绝、原生权限和 Guardian 生命周期。使用临时
  CODEX_HOME 与本机固定响应；不是 Astra 自主任务质量或成本实验。
- 文档更新后再次通过 19 项包契约检查和 manifest 校验；运行代码与 RC2 相同。
- 已安装 RC2 的 74 个 manifest 文件与发布源码摘要一致；稳定 runtime 一致。
- 14 条 RC2 Hook 的保存状态均为 trusted/enabled，无加载警告或错误。
- 已有项目 doctor 返回 GOVERNED、healthy=true、drift=[]，有当前版本/激活的
  SessionStart 记录。这证明该事件已经观察到，不证明每条工具路径都被覆盖。

原始本机检查材料不上传，不包含队友的配置，也不复制私有项目/账本。
本次不重跑真实模型成本实验，不声称稳定 token 降幅、长期无漂移或生产安全全覆盖。
RC2 仍是候选版，适合团队有限试用；原生权限、窄 Gate 与 Agent 判断各有边界。
