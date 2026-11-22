<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/cover-dark.svg">
  <img src="docs/assets/cover-light.svg" width="1280" alt="知微 CosmoPilot V4.0：消费者服务、证据与人工决策">
</picture>

# 知微 CosmoPilot · V4.0

把一通消费者进线，整理成有依据、可复核的服务回复。

[English](README.en.md) · [完整作品集](https://github.com/Daniel-24-life/AIfile) · [AI Coding 实践](docs/ai-coding.md) · [源码阅读路线](docs/source-reading.md)

这是知微 V4.0 产品机制的**离线公开参考版**。围绕五类服务，保留证据分层、消息时点、人工草稿保护和本地反馈闭环。界面、代码与 6 条合成会话面向公开展示重建，不是竞赛原始工程的镜像。

![公开参考工作台的实际运行截图](docs/assets/workbench-desktop.png)

## 先体验这三件事

| 入口 | 具体看什么 | 可参考的机制 |
| --- | --- | --- |
| 日常选品 `DEMO-001` | 对话、证据、缺口与候选回复放在一起 | 买家自述不自动升级成事实；未知信息单列 |
| 高风险服务 `DEMO-002` | 修改草稿后，核对状态失效；核对完成才能采纳 | 人工文本保护、服务端终稿复查、采纳与发送分离 |
| 时点回放 `DEMO-006` | 在第 2 与第 3 条消息之间切换 | 后到的签收证据不会进入更早的分析 |

另外覆盖售后退货、补发换货和订单款项，每条会话都能查看对应证据、缺口和待人工核对的下一步。

## 本地运行

需要 Python 3.11+，无第三方运行依赖、无需模型密钥，也不需要前端构建。

```powershell
python -B app.py
```

访问 <http://127.0.0.1:4188>。如果端口被占用，可运行 `python -B app.py --port 4190`。按 Ctrl+C 停止。

本地反馈保存在被 Git 忽略的 `.runtime/demo.sqlite`。可用 `--db .runtime/another.sqlite` 建立独立演示状态，不会接触原竞赛目录。

## 框架与工程细节

浏览器原生 HTML/CSS/JS → Python 本地 HTTP 服务 → 规则分析与 SQLite。没有外部模型或平台调用。

- **证据可读**：已核对合成记录、买家自述、系统推断三态并列，核验缺口单独显示。
- **过程可查**：六步 Trace 记录实际本地耗时；它不冒充模型推理过程或生产性能成绩。
- **人工文本优先**：新分析与会话切换不会默认覆盖已编辑草稿；高风险草稿修改后重新核对。
- **反馈有状态**：原样采纳、改写采纳和拒绝分别持久化；同键重试不重复写入，过期上下文被拒绝。
- **结果不越界**：本地采纳不改源工单，不代表发送、退款、补发或建单。

公开校验器只有少量演示拦截规则，不能替代原工程完整校验设计、专业审核或生产安全控制。

## AI Coding 与协作

原项目由团队协作完成：本人负责产品、视觉、验收并组织前端实现，技术同学主要负责数据、模型和后端，双方共同联调。本公开版用 AI Coding 辅助整理规格、重建实现和编写测试，范围和发布内容由人确定。

可参考的工作方法是将需求写成输入边界、状态约束和失败用例，再让实现接受测试。详见 [AI Coding 说明](docs/ai-coding.md)，不公开内部 Prompt 链或私人协作记录。

## 测试与阅读

```powershell
python -B -m unittest discover -s tests -v
node --check web/app.js
```

Node.js 22+ 仅用于语法及可选浏览器 QA，不是运行工作台的依赖。

- [架构与状态设计](docs/architecture.md)
- [源码阅读路线](docs/source-reading.md)
- [本轮验证结果](docs/VERIFICATION.md)
- [界面验证](docs/UI_QA.md) · [手机截图](docs/assets/workbench-mobile.png)
- [公开范围](docs/public-scope.md) · [来源与重建说明](docs/provenance.md)

全部数据为新编写的合成样例。未发布官方原件、真实用户资料、原始开发日志或生产执行链。没有官方背书、参赛名次或真实业务效果声明；本轮不新增许可证。
