# Manager Meeting Checklist — 2026-06-17

## Before the Meeting

- [ ] 打开 BTP 线上版本确认可以访问：https://d2slideos.cfapps.eu12.hana.ondemand.com
- [ ] 点"同步 SAC 模型"，确认模型列表正常加载（有进度条）
- [ ] 跑一个 SAC 任务（建议用国泰人寿v1 或 美国地区销售），确认 PPT 能生成
- [ ] 准备好 FUNCTION_SPEC.md 供分享
- [ ] 想好 3 个优先级最高的 pending 问题（见下方）

---

## Demo 流程建议（10-15 分钟）

1. **打开首页** → 展示 SAC 已连接状态
2. **报表库** → 点"同步 SAC 模型"，展示进度条和 AI 中文别名
3. **自然语言建任务** → 输入"帮我分析国泰人寿的数据"，展示模糊匹配警告
4. **手动选模型建任务** → 选国泰人寿v1，立即运行，展示 PPT 生成
5. **运行历史** → 展示历史记录，下载 PPT
6. **定时任务** → 展示 cron 调度配置

---

## 讨论议题

### 已完成功能
- [ ] 介绍 SAC OData 数据对接方案
- [ ] AI 列名推断（ID_xxx → 中文）
- [ ] AI Plotly 图表生成
- [ ] 自然语言建任务 + 模糊匹配提醒
- [ ] BTP 部署上线，代码已推 GitHub

### 待决策问题（需 Manager 输入）

- [ ] **邮件发送**：Resend 不能发 @sap.com，是否接入 SAP 内部 SMTP / Microsoft Graph API？
- [ ] **筛选器个性化分发**：同一个 SAC 模型按不同筛选值分发给不同人（如按大区），是否列入下阶段？
- [ ] **数据库持久化**：每次 BTP push 后 SQLite 会重置，是否需要换成 SAP HANA Cloud 或持久化 volume？
- [ ] 取数问题 现在是直接接入SAC Model API，由AI根据用户的自然语言输入画图 而不是用截图 上线BTP不能实现截图 但是不用截图是不是会丧失SAC最大的功能

### 资源 / 权限
- [ ] 是否有可以用于测试邮件的 SAP SMTP relay 权限？
- [ ] BTP memory 256M 是否够用（AI 生成 + plotly kaleido 渲染较重）？

---

## 会后 Action Items（预留）

| Action | Owner | Due |
|--------|-------|-----|
