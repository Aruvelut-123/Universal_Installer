# Universal Installer

一个基于 Python 和 Qt for Python 的可配置图形安装器。本仓库当前用于构建 **BB+ 汉化模组安装程序**，安装器界面、版本信息和可选组件均由 JSON 配置驱动。

## 功能

- 按平台和 CPU 架构选择安装包（Windows、Linux、macOS）。
- 支持必选组件、可选组件和组件依赖关系。
- 支持 ZIP、RAR、7z、TAR、TAR.GZ 与 TGZ 压缩包。
- 自动查找原生 Steam、Wine、Proton、Winlator 与盖世游戏中的游戏目录。
- 将运行输出和异常分别写入 `logs/` 目录，方便排查问题。

## 环境与系统要求

- Python 3.8
- Windows 7 SP1 或更高版本：发布产物为 x86，可同时运行于 32 位和 64 位 Windows
- Linux x86_64
- macOS 11 或更高版本：发布产物为 Intel x86_64，Apple Silicon 需要 Rosetta 2

Windows 使用 PySide2 5.15.2（Qt 5），Linux 与 macOS 使用 PySide6 6.5.3（Qt 6）。建议为 Windows 7 安装全部系统更新。

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动安装器：

```powershell
python main.py
```

## 兼容环境扫描

自动检测会按以下顺序查找游戏目录：

1. Proton 提供的 `STEAM_COMPAT_INSTALL_PATH` 等环境变量。
2. 原生 Steam 根目录及 `libraryfolders.vdf` 中的全部游戏库。
3. 当前游戏 AppID 对应的 `steamapps/compatdata/<AppID>/pfx` 和 Wine 的 `WINEPREFIX`、`drive_c`、`dosdevices` 映射。
4. Winlator 与 GameSir 盖世游戏容器暴露的 Windows 映射盘，包括常见的 D:、E:、X: 和 Z: 游戏盘。

扫描只检查已知的浅层目录结构，不会递归遍历整块磁盘。在 Winlator 或盖世游戏中使用时，需要在相同容器内运行 Windows 版安装器，并确保游戏目录已映射为容器可访问的盘符。对于直接把游戏根目录映射为盘符的情况，安装器会使用 `game_executable`、`game_executables`，或目录选择提示中的 `.exe` 文件名确认游戏根目录。

Windows 安装器虽然是 x86 程序，但会检测操作系统的原生架构：在 64 位 Windows 上优先使用 `winx64file`，在真正的 32 位 Windows 上使用 `winx86file`。

## 配置文件

| 文件 | 用途 |
| --- | --- |
| `main.py` | 安装器界面、组件选择、路径检测与文件解压逻辑 |
| `metadata_example.json` | 程序名称、版本、权限、图片和注册表等全局配置示例 |
| `pack/items_example.json` | 安装组件、依赖关系、平台文件和目标路径示例 |
| `requirements.txt` | 运行依赖与可选构建依赖 |

使用前请在本地将示例复制为 `metadata.json` 和 `pack/items.json`。这两个本地配置不会提交到 Git。

`pack/items.json` 中每个组件必须具有唯一的 `id`。`dependencies` 中的每个值都必须引用已存在的组件 ID；`files` 和平台文件列表里的每个文件也必须在 `actions` 中配置目标路径。

目标路径可以使用 `{install_path}` 占位符，例如：

```json
{
  "files": ["pack/Example.zip"],
  "actions": {
    "pack/Example.zip": "{install_path}/BepInEx/plugins"
  }
}
```

## 自动构建

GitHub Actions 使用固定架构和版本生成以下产物：

- Windows：Python 3.8.10、PySide2 5.15.2 和 PyInstaller 5.13.2，生成 `main-windows-x86.exe`
- Linux：Python 3.8.18、PySide6 6.5.3 和 Nuitka，生成二进制文件与 AppImage
- macOS：`macos-26-intel`、Python 3.8.18、PySide6 6.5.3 和 Nuitka，生成最低部署目标为 macOS 11 的 x86_64 应用

pip 下载缓存按操作系统、Python 版本、解释器架构和 `requirements.txt` 内容隔离，x86 与 x64 构建不会共用错误的缓存。

## 日志

程序启动后会在 `logs/` 下生成带时间戳的日志：

- `output_*.log`：普通运行输出
- `debug_*.log`：异常与错误信息

提交问题时，请附上对应日志，并说明操作系统、Python 版本和出错步骤。
