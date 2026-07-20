# 移动端生成流程重构

## 结论

移动端的主要问题不是单个模块太高，而是固定头部、长表单、空预览和固定操作栏同时争夺有限视口。改造重点是重新定义信息优先级，而不是全局缩小字号和间距。

## 设计目标

- 在 `≤520px` 视口中，空状态首屏同时露出提示词、素材摘要、输出摘要和预览状态。
- 主生成按钮持续可达，不遮挡最后一项内容。
- 加载、错误、部分失败和结果态不因空状态压缩而丢失信息。
- 任务抽屉的列表区成为主体，头尾只保留必需操作。
- 触控目标不小于 `44px`，支持键盘与 ARIA 状态。

## 前后变化

| 区域 | 改造前 | 改造后 | 原因 |
| --- | --- | --- | --- |
| 站点头部 | 固定 `68px` | 固定 `52px` | 保留品牌识别与 `44px` 任务入口，减少持续占用 |
| 底部生成栏 | 至少 `84px + safe-area` | `68px + safe-area` | 使用 `48px` 按钮与上下 `10px` 间距 |
| 空预览 | 大面积虚线框 | `80px` 横向状态行 | 无结果时不预留无产出价值的画布 |
| 素材与参考 | 参考图和品牌素材默认展开 | 真实 DOM 摘要，按需展开整卡 | 保留可发现性，避免可选内容挤占主流程 |
| 输出设置 | 完整参数表单 | 比例、分辨率、质量、数量摘要 | 高频信息可扫读，低频参数渐进展开 |
| 任务中心顶部 | 标题、搜索、整行新建 | 44px 标题行 + 40px 搜索/筛选行 | 将头部控制在 116px 内 |
| 任务中心底部 | 队列、通知、主题、版本多行 | 单行工具栏 + safe-area | 给任务列表让出高度 |

## 状态模型

### 素材卡

`mobile-materials-expanded` 控制整张卡片，而不是只折叠参考图片。摘要数量来自：

```text
reference image count
+ visible reference file count
+ enabled brand layer count
```

摘要通过现有 `input` / `change` 事件和 `MutationObserver` 同步。标题按钮维护 `aria-expanded` 和 `aria-controls`，桌面端断点始终恢复完整内容。

### 预览区

`mobile-has-preview=false` 仅表示没有加载、错误、等待或结果卡。一旦 `#previewGrid` 出现任一业务状态，布局立即恢复完整预览，避免将生成进度或错误信息压成一行。

### 任务入口

入口使用历史任务图标，队列角标显示“等待数 + 生成中数量”；为零隐藏，超过 99 显示 `99+`。角标与入口的可访问名称共用现有队列状态，不增加后端接口。

## 关键实现

- [移动工作区状态](../codex_image/webui/frontend/src/mobile-workspace.ts)
- [任务抽屉行为](../codex_image/webui/frontend/src/sidebar-drawer.ts)
- [移动端 CSS](../codex_image/webui/static/styles/85-ui-redesign.css)
- [响应式工具样式](../codex_image/webui/static/styles/80-utilities-responsive.css)
- [队列角标同步](../codex_image/webui/frontend/src/queue.ts)

## 验证覆盖

[tests/test_webui_static_mobile_workspace.py](../tests/test_webui_static_mobile_workspace.py) 锁定了：

- 52px 头部、68px 操作栏和 48px 按钮。
- 素材默认折叠、摘要同步、键盘展开和 ARIA 状态。
- 80px 空预览与非空状态恢复。
- 任务抽屉头尾、版本入口搬移/恢复和队列角标。
- `100dvh`、safe-area 和移动端独立滚动容器。

## 边界与下一步

当前验证能证明布局契约和业务状态没有回归，但不能替代真实用户数据。下一步应先测量手机端首次生成时长、高级设置展开率和任务完成率。如果这些指标没有改善，继续压缩像素将是错误方向。
