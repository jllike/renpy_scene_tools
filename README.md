# 汉化素材工具

本目录包含 "Set Yourself on Fire" 的汉化辅助工具链。

## 安装

需要 [uv](https://docs.astral.sh/uv/) 包管理器，安装后依赖会自动管理：

```bash
uv sync
```

## 使用流程

### 1. 安装游戏内采集脚本

将项目放到游戏根目录下

将以下两个 `.rpy` 文件复制到游戏的 `game/` 目录下：

```bash
cp save_scene.rpy ../game/
cp asset_tracker.rpy ../game/
```

### 2. 录制素材

启动游戏，使用快捷键采集素材：

| 快捷键 | 功能 | 输出文件 |
|--------|------|----------|
| **F10** | 开始/停止全程素材录制 | `素材记录.json`（游戏根目录） |
| **F11** | 保存当前屏幕快照 | `快照.json`（游戏根目录） |

**F10 全程录制**：按一次开始，自动记录所有出现的素材；再按一次停止并保存。适合 Ctrl 快速过一遍整个游戏。

**F11 场景快照**：每次按键保存当前屏幕上所有素材的快照（含被遮挡的），适合手动采集特定场景。

### 3. 生成 PSD

将录制好的 `素材记录.json` 放在项目根目录后，运行：

```bash
# 默认：跳过单层场景，使用全部 CPU 核心
uv run make_psd.py

# 只处理原始第 100-119 个场景
uv run make_psd.py --start 100 --count 20

# 包含单层场景（只有背景无文字，对汉化通常无意义，但背景上的文字会被忽略）
uv run make_psd.py --include-single

# 指定并行数
uv run make_psd.py --workers 4
```

输出目录：`psd/<时间戳>/scene_0001.psd, scene_0002.psd, ...`

每个 PSD 包含一个场景：底图为不透明背景，上方叠加透明文字图层，视频素材取中间帧。所有图层左上角对齐 (0,0)，使用无损 RLE 压缩。

### 4. 筛选与复制（基于 F11 快照）

```bash
uv run filter_and_copy.py
```

此工具基于 `快照.json`（F11 快照），执行两步操作：

1. **遮挡筛选**：检测并过滤被遮挡的素材，输出到 `快照_clean.json`
2. **复制素材**：将可见素材按时间戳分组复制到子目录

## 文件说明

| 文件 | 说明 |
|------|------|
| `save_scene.rpy` | F11 场景快照脚本，需复制到 `game/` |
| `asset_tracker.rpy` | F10 全程录制脚本，需复制到 `game/` |
| `filter_and_copy.py` | 快照素材的遮挡筛选与复制 |
| `make_psd.py` | 从素材记录生成场景 PSD |
| `pyproject.toml` | uv 项目配置 |
