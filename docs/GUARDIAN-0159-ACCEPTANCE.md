# Session Guardian / Codex 0.159.2 验收 — 2026-10-02

版本：ACGM for Codex 0.4.0-rc.3。目标是适配本机应用所附的 Codex CLI 0.159.2，
不改变 35% / 20% / 10% 提醒、交接保留预算、继续一次或工作流治理强度。

## 原因与修改

RC2 读取器只接受两个经过验证的旧版本。0.159.2 的原生临时会话仍提供
`session_meta`、`event_msg/token_count` 和 `token_usage_record`，字段无需转换。
捕获样本的最近用量为 1020，累计为 2040，有效窗口为 475000；回归确保不将
累计花费当作当前上下文。生产读取器只新增精确的 `0.159.2`，不接受未验证的后继版本。

修复前，用真实样本的回归在 `Unverified rollout version: 0.159.2` 处失败；
原生 Harness 的普通 Gate/审批场景仍能通过，但启用 Guardian 后暂停请求，
导致低用量工作、继续一次、交接、自动压缩边界和新会话验收失败。
这是保守的未验证版本拒绝，不是已经证实的协议破坏。

增加的代码主要用于真实指标捕获、验收断言和 RC2 精确升级 pin。
没有更改 session_hooks 状态机、风险 Gate、项目策略或原生权限。
Hook 定义因为绑定源码摘要而重生成；升级必须重启并由用户重新信任。

## 验证方法

```sh
python3 scripts/release_check.py --json
python3 tests/native_harness.py --output /tmp/acgm-native.json \
  --metrics-output /tmp/acgm-native-metrics.json
```

Harness 使用独立临时 CODEX_HOME、本机固定 Responses 与 synthetic 文件，
不消费真实模型用量。原生 sandbox/approval 控制保留，临时受审 Hook 的信任跳过
只作用于该次测试调用，不能代替实际用户信任。指标导出只含允许的字段，
不保存用户会话、prompt、工具内容或真实路径。

当前 Codex 不再附带旧 plugin-creator 校验脚本。发布检查在其缺失时运行已有
包契约测试并明确标记 `plugin_contract:repository`，不会宣称官方 validator 通过；
若脚本存在仍优先使用。仓库契约失败仍使发布失败。真实安装/加载需另行核对。

## 安装与结论边界

源码发布检查通过：256 项测试（149.959 秒）、6 个技能契约、19 项仓库包契约和
manifest 校验。原生 0.159.2 验收通过 28 场景 / 32 条断言，包括已送达的
35%/20% 提醒、缓冲门、继续一次、下一条请求阻断、交接、自动压缩前停止、
新会话、原生批准/拒绝、执行成功/失败对账及不调用模型的 dashboard。
指标 fixture 与旧版本 fixture 均保留；未知 0.159.3 的负例继续拒绝。

从精确发布标签运行插件升级，保留用户项目文件、账本与 Guardian 未完成请求；
不批量重新激活项目。安装后完全退出并重开 Codex，在设置里审阅新版 Hooks。
第一次正常工作中实际观察到的 Hook 才能完成运行验收。

本轮不是 Astra 长任务语义质量或节省 token 的实验，也不验证所有未来 Codex
版本。内部 rollout 格式仍需逐版本核对；未知、损坏和缺少观测不能标成健康。
