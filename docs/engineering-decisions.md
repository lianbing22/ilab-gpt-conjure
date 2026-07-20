# 关键工程决策

## ED-001：Logo/Slogan 不进入生成提示词

**决策**：品牌标识使用生成后确定性合成。

**原因**：生成模型会将 Logo 和 Slogan 当作可解释的视觉元素，可能改字、变形、改色或生成伪标识。品牌一致性是约束问题，不是创意生成问题。

**取舍**：后处理无法像模型一样理解复杂画面语义，需要明确的布局、对比度和遮罩策略。换来的是可重复、可测试和可审计。

**实现**：[compositor.py](../codex_image/branding/compositor.py)、[contrast.py](../codex_image/branding/contrast.py)、[placement.py](../codex_image/branding/placement.py)。

## ED-002：原图不可变，品牌图是派生物

**决策**：不原地覆盖生成结果。

**原因**：用户需要比较原图和品牌图，失败后也应保留已成功的生成产物。原地覆盖会使后处理错误变成不可逆数据丢失。

**取舍**：需要额外存储空间和双版本前端交互。但它显著降低了恢复成本，并使处理过程可追溯。

**实现**：[TaskStorage.write_branded_output](../codex_image/webui/storage.py) 和 [brand-result-actions.ts](../codex_image/webui/frontend/src/brand-result-actions.ts)。

## ED-003：用请求哈希建立幂等，不依赖临时进程状态

**决策**：由原图内容、品牌模板版本和素材内容计算 `request_hash`。

**原因**：队列恢复、进程崩溃或用户重试都可能重复触发后处理。内存布尔标志无法跨重启保存，也不能证明输入未变。

**取舍**：计算哈希有少量 I/O 成本，但避免重复产物和不可识别的旧结果。

**实现**：[BrandingService._brand_one](../codex_image/branding/service.py)。

## ED-004：逐图失败隔离

**决策**：多结果任务中，每张品牌图独立处理和记录错误。

**原因**：单张图的读取、素材或合成异常不应撤销其他已成功交付物。

**取舍**：任务状态从简单成功/失败扩展为 `partial_failed`，前端和测试需处理更多分支。

**实现**：[BrandingService.apply_task_branding](../codex_image/branding/service.py) 和 [test_branding_service.py](../tests/test_branding_service.py)。

## ED-005：任务级锁保护完整读-改-写

**决策**：所有并发元数据变更通过 `update_metadata` 在每任务 `RLock` 内完成。

**原因**：只保护最后的 `write` 不能防止丢失更新。两个写者可同时读到相同旧副本，之后顺序写入，后写者仍会覆盖前者的业务变更。

**取舍**：同一任务的元数据变更串行化，但不同任务仍可并发。`RLock` 允许存储内部调用重入，避免将锁细节泄露到业务层。

**实现**：[storage.py](../codex_image/webui/storage.py) 和 [test_webui_storage_concurrency.py](../tests/test_webui_storage_concurrency.py)。

## ED-006：移动端优先渐进披露，不做桌面表单等比缩放

**决策**：高频主任务始终可见，可选素材和低频参数以可扫读摘要默认折叠。

**原因**：单纯缩小间距会降低可读性和触控可用性，却不会改变主次关系。

**取舍**：折叠状态需要摘要同步、ARIA 和键盘交互；同时必须确保加载/错误/结果态不被压缩。

**实现**：[mobile-workspace.ts](../codex_image/webui/frontend/src/mobile-workspace.ts) 和 [test_webui_static_mobile_workspace.py](../tests/test_webui_static_mobile_workspace.py)。

## 未采用方案

| 方案 | 未采用原因 |
| --- | --- |
| 让模型在生成时直接画 Logo | 无法保证文字、形状、颜色和间距一致 |
| 在前端 Canvas 临时叠加 | 历史任务、批量下载、恢复和服务端交付无法共享真实产物 |
| 覆盖原图节省存储 | 任何后处理错误都会不可逆，也无法比较原图 |
| 仅给 `write_metadata` 加锁 | 无法保护锁之前的旧数据读取，仍会丢失业务更新 |
| 立即重写 React Native / Flutter | 尚未用真实完成率证明原生重写是主要瓶颈 |
