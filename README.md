# Universal Installer

一个基于 Python 和 PySide6 的可配置图形安装器。本仓库当前用于构建 **BB+ 汉化模组安装程序**，安装器界面、版本信息和可选组件均由 JSON 配置驱动。

## 功能

- 按平台和 CPU 架构选择安装包（Windows、Linux、macOS）。
- 支持必选组件、可选组件和组件依赖关系。
- 支持 ZIP、RAR、7z、TAR、TAR.GZ 与 TGZ 压缩包。
- 自动查找 Steam 与游戏安装目录。
- 将运行输出和异常分别写入 `logs/` 目录，方便排查问题。

## 环境要求

- Python 3.12 或更高版本
- Windows 为当前主要运行平台；代码也包含 Linux 和 macOS 的安装包选择逻辑

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动安装器：

```powershell
python main.py
```

## 配置文件

| 文件 | 用途 |
| --- | --- |
| `main.py` | 安装器界面、组件选择、路径检测与文件解压逻辑 |
| `metadata.json` | 程序名称、版本、权限、图片和注册表等全局配置 |
| `pack/items.json` | 安装组件、依赖关系、平台文件和目标路径 |
| `requirements.txt` | 运行依赖与可选构建依赖 |

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

## 日志

程序启动后会在 `logs/` 下生成带时间戳的日志：

- `output_*.log`：普通运行输出
- `debug_*.log`：异常与错误信息

提交问题时，请附上对应日志，并说明操作系统、Python 版本和出错步骤。
