# 下载 / Releases

当前正式版本：[v0.5.6](https://github.com/kadevin/ilab-gpt-conjure/releases/tag/v0.5.6)

## 版本说明

当前版本：`v0.5.6`。这个版本聚焦 WebUI 体验打磨、PWA 区分、历史库稳定性、提示词模板库和系统设置细节。新用户建议下载标准包：macOS 使用 DMG，Windows 使用独立 App ZIP；老用户和调试用户仍可下载 portable zip 继续沿用同目录 `data/` 工作流。

本版重点：0.5.6 改进 PWA 名称、图标、标题和缓存；修复历史库中文搜索、任务切换闪烁、方向键导航、缩略图比例和生成页筛选误判；优化提示词面板、模板库瀑布流、搜索清空和详情操作；打磨系统设置深色主题、API 供应商编辑态、API Key 临时查看和主题切换闪色；同时修复取首图尺寸约束、完成任务计时残留、筛选面板遮挡、浅色任务卡 hover 边界和资源管理按钮一致性。

本版详情：

### 升级必读

- `v0.5.4` 及更早 portable 用户首次升级到 `0.5.5` 时，建议手动下载完整标准包或完整 portable 包；旧 updater 只保证升级 WebUI/依赖，不保证安装新的小兔子启动器、标准 `.app` / `.exe` 入口和迁移助手。
- 新用户建议优先下载标准包。标准包把用户数据写入系统应用数据目录；portable 包继续把数据写在同级 `data/`，用于老用户过渡、调试和临时工作流。
- 标准包检查更新目前只打开 GitHub Release 页面；未签名 `.app` 和 Windows ZIP 的自替换更新器延后，避免扩大文件替换风险。
- macOS 标准 DMG 和 portable zip 都暂未签名、未 notarize，首次启动可能需要右键或 Control-click 选择 Open。

### PWA、图标和标准应用包

- 新增项目 favicon，首页和历史库页面都会显示小兔子图标。
- PWA 使用独立名称 `iLab CONJ Web`，并用白底绿色 `W` 标识区分 Web 版和原生 App；原生 App 图标保持小兔子主体不变。
- 修复 PWA / standalone 窗口标题重复显示品牌名的问题，浏览器标签页仍保留完整产品名。
- 修复 service worker 对带版本参数资源的缓存问题，减少 PWA 命中旧脚本、旧图标和旧 manifest 的概率。
- 标准包继续提供 macOS Apple Silicon DMG、macOS Intel DMG 和 Windows x64 标准 App ZIP；用户数据目录和旧 portable 数据确认复制迁移规则保持不变。
- 如果 Launchpad 出现重复图标或搜索异常，通常是同时安装 PWA、挂载多个测试 DMG 或本机 LaunchServices 记录残留；先推出 DMG 并移除旧 PWA。

### portable 过渡包与自动更新

- 继续保留三种 portable zip：Windows x64、macOS Apple Silicon、macOS Intel；portable 数据仍保存在包内同级 `data/`。
- portable 包包含 `Start iLab GPT CONJURE.exe` / `Start iLab GPT CONJURE.app` 启动器，旧的 `Start WebUI Portable` 脚本继续保留作为终端调试入口。
- portable 自动更新使用 signed `latest.json` manifest、Ed25519 签名校验、SHA256 校验、`.backup/` 备份和更新后重启；`latest.json` 只声明 portable 三平台 zip，不作为标准包自替换更新 manifest。
- 更新器只替换一键包目录内由程序管理的文件，保留本地 `data/`，并在执行前显示所选资产和 manifest SHA256。

### 生成页与任务状态

- `取首图` 写入自定义比例后会自动把像素尺寸归一到 `gpt-image-2` 合法范围，避免出现低于最小像素或不满足 16 倍数约束的尺寸。
- 刷新任务时会同步刷新队列，任务自身已经进入完成 / 失败 / 部分失败终态时，不再被残留 running 队列状态覆盖成计时中。
- 左侧任务搜索新增独立清空按钮；有搜索内容时即使输入框失焦也保持可见。
- 搜索结果分组在输入变化时直接保持展开态，不再出现快速收起再展开的箭头动画。
- 输出设置里的方向选项新增轻量方向图标，与历史库筛选栏保持一致。
- 任务筛选面板改为搜索框下方内联面板，不再作为 absolute 浮层遮挡第一条任务。
- 浅色主题下普通任务卡 hover 时增加轻量边界反馈，默认状态仍保持低噪声列表密度。

### 历史库

- 历史库搜索在 SQLite FTS 基础上补充中文子串匹配，搜索“详情”等中文片段不再漏掉“电商详情页”任务。
- 切换历史任务详情时保留当前预览，等待新任务图片预加载并解码后再替换，减少右侧详情闪烁。
- 历史库任务卡键盘导航修复：列表模式支持上下切换，网格模式支持上下左右按实际屏幕位置切换。
- 修复任务卡 active 描边和键盘焦点描边叠加导致的双描边。
- 历史索引优先使用实际输出尺寸来计算缩略图比例，减少因为请求尺寸和实际输出尺寸不一致导致的上下白边。
- 生成页侧栏筛选优先使用任务请求尺寸；如果供应商返回了不同尺寸，不会把请求 `9:16` 但实际约分为 `2:3` 的任务误归入 `2:3`。

### 提示词与模板库

- 提示词对比面板按当前图片真实可见区域居中，而不是按底部按钮位置居中。
- 提示词浮层使用稳定可读宽度，双图窄屏时两个面板不再一宽一窄；复制按钮移到“优化后提示词”标题行，缩短操作路径。
- 预览卡片的提示词相关按钮在窄宽度下固定为 `2 + 2` 布局，避免出现 `3 + 1` 排列。
- 提示词编辑器内方向键只在编辑器内移动光标，不会冒泡触发任务卡切换；恢复和粘贴长提示词时统一用 `<br>` 渲染换行，减少 WebKit 光标跳位。
- 模板库搜索框新增内嵌清空按钮，清空后焦点仍留在搜索框。
- 模板库改为两列瀑布流，封面按原图比例显示，不再固定裁剪为 4:3。
- 模板副标题为空或与标题相同时不再重复显示；模板详情页顶部导航和底部复制 / 插入 / 替换按钮权重重新整理。

### 系统设置与 API 配置

- 修复深色主题下系统设置 Tab、API 供应商选中卡片和 Codex 通道当前徽标的文字颜色对比。
- API 供应商编辑表单改为左右等宽；供应商较多时，编辑态列表变为局部滚动，不再把编辑表单和按钮挤到页面下方。
- API Key 输入框新增眼睛按钮，可临时查看当前输入值；已保存但后端未回显的完整 key 不会被泄露到前端。
- 并发数输入去掉浏览器原生 spinner，避免深色主题下颜色突兀。
- “取消编辑 / 保存供应商”统一为居中、同尺寸、同圆角按钮。
- 切换浅色 / 深色主题时短暂禁用颜色过渡，避免变量切换时出现异常混合色闪烁。

### 结构维护与发布工作流

- 统一“管理公用库”和“管理模板库”按钮规格、图标、尺寸和样式。
- 拆分原 4000+ 行 `70-settings-preview.css`，按输出设置、预览结果、队列弹窗、图库抽屉、API 设置、图片编辑器等职责重新组织 CSS 分片。
- 补充覆盖取首图尺寸、任务终态、历史搜索、历史切换、方向键、模板库、系统设置和 PWA 标题的回归测试。
- `0.5.4` 用户通过 portable 更新到 `0.5.5` 或更新版本后，会弹出标准包过渡说明，提示标准 App、portable 数据目录和迁移助手的区别。

### 发布工作流

- Release workflow 同时构建并上传 macOS Apple Silicon DMG、macOS Intel DMG、Windows 标准 App ZIP、Windows x64 portable、macOS Apple Silicon portable、macOS Intel portable、所有 `.sha256.txt` 和 portable 用 `latest.json`。
- `latest.json` 仅服务 portable 自动更新；标准包下载信息放在 Release 正文和 README 中。

## 推荐下载

| 平台 | 推荐给 | 下载 | SHA256 |
| --- | --- | --- | --- |
| macOS Apple Silicon | 新用户，M1/M2/M3/M4 | [iLab-GPT-CONJURE-macos-arm64-0.5.6.dmg](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-macos-arm64-0.5.6.dmg) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-macos-arm64-0.5.6.dmg.sha256.txt) |
| macOS Intel | 新用户，Intel x64 | [iLab-GPT-CONJURE-macos-x64-0.5.6.dmg](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-macos-x64-0.5.6.dmg) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-macos-x64-0.5.6.dmg.sha256.txt) |
| Windows x64 | 新用户，Windows 10/11 x64 | [iLab-GPT-CONJURE-windows-x64_0.5.6.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-windows-x64_0.5.6.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/iLab-GPT-CONJURE-windows-x64_0.5.6.zip.sha256.txt) |

标准包数据目录：

- macOS：`~/Library/Application Support/iLab GPT CONJURE/`
- Windows：`%APPDATA%\iLab GPT CONJURE\`

标准包的“检查更新”会打开 Release 页面。目前不对标准 `.app` 或 Windows 标准 ZIP 执行自动自替换。

## 免安装一键包

| 平台 | 适用设备 | 下载 | SHA256 |
| --- | --- | --- | --- |
| Windows x64 | Windows 10/11 x64 | [ilab-gpt-conjure_windows_portable_x64_0.5.6.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_windows_portable_x64_0.5.6.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_windows_portable_x64_0.5.6.zip.sha256.txt) |
| macOS Apple Silicon | M1/M2/M3/M4 | [ilab-gpt-conjure_macos_portable_arm64_0.5.6.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_macos_portable_arm64_0.5.6.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_macos_portable_arm64_0.5.6.zip.sha256.txt) |
| macOS Intel | Intel x64 | [ilab-gpt-conjure_macos_portable_x64_0.5.6.zip](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_macos_portable_x64_0.5.6.zip) | [sha256](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/ilab-gpt-conjure_macos_portable_x64_0.5.6.zip.sha256.txt) |

portable 自动更新 manifest：

- [latest.json](https://github.com/kadevin/ilab-gpt-conjure/releases/download/v0.5.6/latest.json)

使用方式：

1. 下载对应平台的 zip。
2. 解压到普通用户目录，不要放在系统保护目录。
3. Windows 双击 `Start iLab GPT CONJURE.exe`；macOS 双击
   `Start iLab GPT CONJURE.app`。旧的 `Start WebUI Portable.bat` /
   `Start WebUI Portable.command` 仍保留，用于终端调试。
4. 如果浏览器没有自动打开，访问 `http://127.0.0.1:8787/`。

一键包启动器不会后台自动访问 GitHub。更新已经解压的一键包时，可在托盘 / 菜单栏
菜单选择检查更新，并在发现新版本后确认 `安装更新`；也可以退出启动器后手动运行
Windows 的 `Update WebUI Portable.bat` 或 macOS 的 `Update WebUI Portable.command`。
更新脚本会读取带签名的 `latest.json`
manifest，先用启动器内置公钥校验 Ed25519 签名，再下载当前平台对应的最新
GitHub Release 资产，执行前显示所选资产和 manifest SHA256，校验下载 zip 的
SHA256，只替换一键包目录内由程序管理的文件，保留本地 `data/`，并把被替换文件备份到 `.backup/`。

macOS 标准 DMG 和 portable zip 都暂未签名、未 notarize。如果 macOS
拦截启动，可以右键或 Control-click App，选择 Open，并在系统安全提示中再次确认。
portable zip 也可以对解压目录执行：

```bash
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_arm64
# 或：
xattr -dr com.apple.quarantine /path/to/ilab-gpt-conjure_macos_portable_x64
```

一键包内的 `data/` 目录会保存本地设置、公用图库、输入图、输出图、任务数据库和日志。
不要把这些本地数据、API key 或 OAuth 文件提交到 Git。
