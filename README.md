# Universal Installer

A general-purpose GUI installer framework built with Python and PySide6 (Qt).  
Pack your application files into the specified structure and Universal Installer will handle the rest — component selection, dependency resolution, archive extraction, and Windows registry integration.

## Features

- **Component-based installation** — Define installable components with dependencies, incompatibilities, and per-architecture files (`x64`/`x86`)
- **Multi-format archive support** — Extracts `.zip`, `.rar`, `.7z`, and `.tar.gz` archives
- **Steam auto-detection** — Automatically locates game install paths by parsing Steam's `libraryfolders.vdf`
- **Disk space validation** — Calculates required space from archive contents before installation
- **Windows registry integration** — Creates install/uninstall registry entries for Add/Remove Programs
- **Customizable UI** — Configure program name, icons, banners, license text, and footer info via `metadata.json`
- **Uninstaller generation** — Automatically creates an uninstaller that lets users selectively remove components; cleans up registry when core components are removed
- **PyInstaller packaging** — Build script to produce standalone `.exe` binaries for both installer and uninstaller

## Project Structure

```
├── main.py              # Main GUI application and installation logic
├── uninstaller.py       # Uninstaller GUI application
├── build.py             # Build script for packaging with PyInstaller
├── metadata.json        # Installer configuration (name, version, UI assets, etc.)
├── requirements.txt     # Python dependencies
└── pack/
    ├── items.json       # Component manifest (files, dependencies, actions)
    └── ...              # Archive files, icons, license, images
```

## Component Configuration (`pack/items.json`)

Each component in `items.json` supports the following attributes:

| Attribute | Type | Description |
|---|---|---|
| `name` | string | Display name shown in the installer |
| `id` | string | Unique identifier for the component |
| `desc` | string | HTML description shown on hover |
| `required` | bool | If `true`, the component cannot be unchecked |
| `checked` | bool | Default checked state |
| `part_checked` | bool | If `true`, shows partial check state |
| `disabled` | bool | If `true`, the component is greyed out |
| `after` | string/null | Parent component ID (for tree nesting) |
| `dependencies` | list | List of component IDs that must also be installed |
| `incompatible` | list | List of component IDs that conflict with this one |
| `files` | list/null | Archive files to extract |
| `x64file` | list | Files only for 64-bit systems |
| `x86file` | list | Files only for 32-bit systems |
| `actions` | object/null | Maps each file to its extraction destination path |

## Requirements

- Python 3.13+
- Windows (uses `winreg`, `ctypes` for admin elevation)
- Dependencies listed in `requirements.txt`

## Usage

1. Place your archive files and assets in the `pack/` directory
2. Configure `metadata.json` with your application details
3. Define your components in `pack/items.json`
4. Run `python main.py` to launch the installer
5. Use `python build.py` to package into standalone `.exe` binaries (installer + uninstaller)

## Uninstaller

During installation, the installer saves an `install_manifest.json` to the install directory and copies `Uninstall.exe` alongside it.  
The uninstaller reads this manifest to present a component selection tree.

- Select which components to remove
- If the **core component** (defined by `main_item` in `metadata.json`) is removed, the Windows registry entries are also cleaned up
- After partial uninstall, the manifest is updated to reflect the remaining components        
