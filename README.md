# Universal Installer

一个基于 Python 和 Qt for Python 的可配置图形安装器。本仓库当前用于构建 **BB+ 汉化模组安装程序**，安装器界面、版本信息和可选组件均由 JSON 配置驱动。

## 功能

- 按平台和 CPU 架构选择安装包（Windows、Linux、macOS）。
- 支持必选组件、可选组件和组件依赖关系。
- 每个含文件的组件具有独立版本号，安装信息会记录组件版本和文件归属。
- 支持 ZIP、RAR、7z、TAR、TAR.GZ 与 TGZ 压缩包。
- 自动查找原生 Steam、Wine、Proton、Winlator 与盖世游戏中的游戏目录。
- 更新已有安装时精确替换所选组件：删除旧版遗留文件、替换变更文件，并通过 SHA-256 跳过内容未变化的文件。
- 卸载器允许选择组件；卸载依赖时会警告并自动勾选依赖它的组件，共享文件和未选择组件会保留。
- 安装完成后保存精确文件清单，并提供 Windows、Linux 与 macOS 卸载器；被覆盖的原文件会在卸载时恢复。
- Windows 会在“程序和功能”中注册卸载项并指向随程序安装的卸载器。
- 将运行输出和异常分别写入 `logs/` 目录，方便排查问题。

## 环境与系统要求

- Python 3.8
- Windows 7 SP1 或更高版本：发布产物为 x86，可同时运行于 32 位和 64 位 Windows
- Linux i686（32 位 x86）或兼容 32 位程序的 x86_64 系统
- macOS 11 或更高版本：发布产物为 Intel x86_64，Apple Silicon 需要 Rosetta 2

Windows 与 Linux i686 发布构建使用 PySide2/Qt 5，macOS 使用 PySide6/Qt 6。建议为 Windows 7 安装全部系统更新。

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
| `uninstaller.py` | 安装事务记录、原文件备份、控制面板注册与安全卸载逻辑 |
| `platform_utils.py` | 安装/卸载共享的运行路径、响应式 Qt 界面、像素画缩放与 Windows 原生集成 |
| `metadata.json` | 本地 BB+ 安装器配置（不提交） |
| `pack/items.json` | 本地 BB+ 组件、版本、依赖、平台文件和目标路径配置（不提交） |
| `metadata_example.json` | 可复用的通用全局配置示例 |
| `pack/items_example.json` | 可复用的通用组件配置示例 |
| `requirements.txt` | 运行依赖与可选构建依赖 |

首次使用或复用本项目时，将两个示例文件复制为 `metadata.json` 和 `pack/items.json`，再替换示例值。这两个生产配置和 `build.py` 仅保存在本地，不会提交到 Git。

`pack/items.json` 顶层使用 `components`。每个组件必须具有唯一的 `component_id`；`dependencies` 中的每个值都必须引用已存在的组件 ID。含文件的组件必须提供非空 `version`，只用于分组且没有文件的组件可省略版本。`common_files` 和平台文件列表里的每个文件也必须在 `destinations` 中配置目标路径。

顶层 `uninstaller` 对象分别配置 Windows、Linux 和 macOS 的卸载器包。其中 `source_file` 是随组件分发的源文件，`installed_executable` 是安装完成后的可执行文件相对路径。卸载器必须放入必选组件对应的平台文件列表，并在 `destinations` 中安装到 `{install_path}`。生产配置让 `main` 核心拥有卸载器，因此移除核心时也会移除卸载器和 Windows 注册表项；BepInEx 由独立组件拥有并会保留。

`metadata.json` 中的 `product_registry_key` 与 `uninstall_registry_key` 是可复用安装器时必须自行设置的完整注册表路径，均位于 `Software\...` 下。组件可使用 `is_core_component` 明确标记核心（省略时默认为 `false`，旧配置继续回退到 `core_component_index`）；移除核心会删除卸载器、`.universal_installer` 和 Windows 注册项，即使其他独立组件仍然保留。Windows 卸载器保持为单个 PyInstaller one-file EXE，核心卸载后会在进程退出时删除自身。安装完成后，组件版本、依赖、文件 SHA-256、文件归属和原文件备份索引保存在 `{install_path}/.universal_installer/install_info.uim`；许可证、图标和可用的页眉/侧栏图片也会复制到同目录的 `ui` 文件夹，供独立卸载器使用。安装信息是带版本标识并使用 zlib 压缩的专用二进制格式，不是明文 JSON。

组件可使用 `remove_directories_on_uninstall` 指定卸载该组件时需递归清理的生成目录，例如 `"{install_path}/plugins/application-core"`。路径必须严格位于安装目录内，不能指向安装根目录、安装信息目录或通过链接逃逸；目录内未由安装器记录的文件也会删除，因此只应配置该组件独占的目录。

目标路径可以使用 `{install_path}` 占位符，例如：

```json
{
    "common_files": [
        "pack/Example.zip"
    ],
    "destinations": {
        "pack/Example.zip": "{install_path}/BepInEx/plugins"
    }
}
```

旧版键名（如 `items`、`id`、`name`、`files`、`actions`）仍可读取，以便旧安装包平滑迁移；新配置应使用示例中的可读键名。

## 自动构建

GitHub Actions 使用固定架构和版本生成以下产物：

- Windows：Python 3.8.10、PySide2 5.15.2 和 PyInstaller 5.13.2，生成 `main.exe`
- Linux：Debian i386 容器、PySide2/Qt 5 和 PyInstaller 5.13.2，生成真实的 i686 `main.bin`
- macOS：`macos-26-intel`、Python 3.8.18、PySide6 6.5.3 和 PyInstaller 5.13.2，生成最低部署目标为 macOS 11 的 x86_64 应用

安装器的三个主产物固定命名为 `main.exe`、`main.bin` 和 `macos.zip`。同一批构建还会生成 `uninstall-windows-x86.exe`、`uninstall-linux-x86.bin` 和 `uninstall-macos.zip`。Windows 与 Linux 卸载器是可直接分发的单文件程序。x86 和 x64 Linux 都安装同一个 i686 卸载器，但 BepInEx 等运行时仍按宿主架构选择 x86 或 x64 产物。组装安装包时，应将默认产物放到 `pack/items.json` 的 `uninstaller.*.source_file` 指定位置。

安装器和卸载器不强制使用 Fusion 或自定义 Qt 主题，而是保留当前平台提供的原生控件样式、字体和调色板。Windows 构建优先使用 Qt 的 `windowsvista` UxTheme 样式，因此 Windows 7 的 Aero、Windows 8/8.1 的 Metro、Windows 10 的 Fluent 外观和 Windows 11 的当前系统外观会由宿主系统决定；Windows 11 还会在支持时请求原生圆角和 Mica，失败时自动保留普通系统窗口。macOS 和 Linux 同样使用各自 Qt 平台插件提供的默认样式，显式设置的 `QT_STYLE_OVERRIDE` 会被保留。

Linux 构建不设置 `QT_QPA_PLATFORM`，由 Qt 根据宿主会话和用户环境变量自动选择显示后端。

pip 下载缓存按操作系统、Python 版本、解释器架构和依赖清单内容隔离。Linux i686 作业会将容器内构建好的 wheel 仓库挂载到 Actions 缓存，后续作业可直接从本地 wheel 安装，不必重新下载或构建 Python 包。

Windows、Linux 和 macOS 构建统一使用 PyInstaller。Actions 按操作系统、Python 版本、解释器架构和依赖清单隔离 pip 下载缓存，并为每个平台及安装器/卸载器作用域分别持久化 PyInstaller 增量工作目录。构建不会使用 `--clean` 主动清空缓存。

## 日志

程序启动后会在 `logs/` 下生成带时间戳的日志：

- `output_*.log`：普通运行输出
- `debug_*.log`：异常与错误信息

提交问题时，请附上对应日志，并说明操作系统、Python 版本和出错步骤。
