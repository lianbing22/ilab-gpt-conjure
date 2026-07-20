# 测试策略与验证命令

## 结论

测试围绕“用户交付物不丢失”建立：合成算法要可重复，品牌后处理要可部分失败，元数据并发更新不能互相覆盖，移动端压缩不能隐藏生成中和错误状态。

## 分层覆盖

| 层级 | 主要风险 | 对应测试 |
| --- | --- | --- |
| 纯合成算法 | 布局、色调选择、比例、边界和输出模式错误 | [test_branding.py](../tests/test_branding.py) |
| 品牌服务 | 覆盖原图、重复处理、单图失败中断批次、崩溃后无法恢复 | [test_branding_service.py](../tests/test_branding_service.py) |
| 素材与模板 | 内容变化不可追溯、无效素材恢复 | [test_webui_brand_assets.py](../tests/test_webui_brand_assets.py) · [test_webui_brand_templates.py](../tests/test_webui_brand_templates.py) |
| API 与任务运行时 | 入队未冻结、路由参数丢失、部分失败状态错误 | [test_webui_generation.py](../tests/test_webui_generation.py) · [test_webui_brand_routes.py](../tests/test_webui_brand_routes.py) |
| 存储并发 | 丢失更新、半写入 JSON、索引失败掩盖真实文件 | [test_webui_storage_concurrency.py](../tests/test_webui_storage_concurrency.py) |
| 移动端契约 | 固定尺寸回归、摘要不同步、ARIA 错误、结果态被压缩 | [test_webui_static_mobile_workspace.py](../tests/test_webui_static_mobile_workspace.py) |
| 版本与缓存 | 展示版本、更新历史和 Service Worker 缓存不一致 | [test_webui_settings.py](../tests/test_webui_settings.py) · [test_webui_static_pwa.py](../tests/test_webui_static_pwa.py) |

## 可复现命令

### 前端类型检查与构建

```bash
npm ci
npm run check:webui
git diff --exit-code -- codex_image/webui/static
```

`check:webui` 依次运行：

1. CSS 模块合并与 manifest 构建。
2. TypeScript `--noEmit` 类型检查。
3. esbuild 生成 `app.js` / `history.js` 和 source map。

### 品牌与存储高风险回归

```bash
.venv/bin/python -m pytest -q \
  tests/test_branding.py \
  tests/test_branding_service.py \
  tests/test_webui_brand_assets.py \
  tests/test_webui_brand_routes.py \
  tests/test_webui_brand_templates.py \
  tests/test_webui_generation.py \
  tests/test_webui_storage_concurrency.py
```

### 移动端、布局、国际化与 PWA

```bash
.venv/bin/python -m pytest -q \
  tests/test_webui_static_mobile_workspace.py \
  tests/test_webui_static_layout.py \
  tests/test_webui_static_i18n.py \
  tests/test_webui_static_pwa.py
```

### 全量回归

```bash
.venv/bin/python -m pytest -q
```

GitHub Actions 额外在 Python 3.11、3.12 和 3.13 上执行 `unittest discover`，并独立验证前端生成物无未提交差异。

本次仓库改造的本地全量结果为 `838 passed, 1 skipped, 338 subtests passed`。macOS 自带 LibreSSL 不支持签名测试使用的 `pkeyutl -rawin`，因此本地全量命令使用 Homebrew OpenSSL 3：

```bash
PATH=/opt/homebrew/opt/openssl@3/bin:$PATH .venv/bin/python -m pytest -q
```

## 并发回归的关键断言

并发测试不只检查“最终 JSON 能解析”，还需同时证明：

- 两个业务写者的字段都存在，不是最后写者覆盖前者。
- 读者在密集写入期间始终只看到完整 JSON。
- 不同任务锁不互相阻塞。
- SQLite 索引 upsert 异常不会伪装成元数据文件写入失败。
- 品牌后处理与归档/任务状态更新并发时，各自变更都被保留。

## 前端契约测试的边界

静态契约测试适合锁定断点、CSS 变量、DOM 钩子、ARIA 和事件路径，但无法完全证明真实浏览器中无重叠、无截断。因此发布前仍需在 `320×700`、`360×800`、`390×844`、`521px` 和桌面断点执行截图/交互检查，并覆盖空状态、素材展开、加载、错误、已有结果和长任务列表。
