#!/bin/bash
set -euo pipefail

target=${1:-}
if [[ "$target" != "installer" && "$target" != "uninstaller" ]]; then
  echo "Usage: $0 installer|uninstaller" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
export PIP_CACHE_DIR=${PIP_CACHE_DIR:-/pip-cache}
export PIP_WHEEL_DIR=${PIP_WHEEL_DIR:-$PIP_CACHE_DIR/wheels}
export PYINSTALLER_WORKPATH=${PYINSTALLER_WORKPATH:-/pyinstaller-work/$target}
mkdir -p "$PIP_CACHE_DIR" "$PIP_WHEEL_DIR" "$PYINSTALLER_WORKPATH"

apt-get update -qq
apt-get install -y --no-install-recommends \
  binutils ca-certificates file patchelf \
  python3 python3-pip \
  python3-pyside2.qtcore python3-pyside2.qtgui python3-pyside2.qtwidgets \
  libegl1 libgl1 libopengl0 libxkbcommon0 libxkbcommon-x11-0 \
  libdbus-1-3 libxcb1 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xfixes0 libxcb-xkb1

python3 -m pip wheel \
  --find-links "$PIP_WHEEL_DIR" \
  --wheel-dir "$PIP_WHEEL_DIR" \
  -r requirements-linux-x86.txt
python3 -m pip install \
  --no-index \
  --find-links "$PIP_WHEEL_DIR" \
  -r requirements-linux-x86.txt
python3 -m pip cache info || true

verify_i386() {
  file "$1" | tee /dev/stderr | grep -Eq "ELF 32-bit.*Intel 80386"
}

smoke_test() {
  local executable=$1
  local status=0
  timeout 20s env QT_QPA_PLATFORM=offscreen "$executable" || status=$?
  if [[ "$status" -ne 0 && "$status" -ne 124 ]]; then
    echo "Linux binary smoke test failed with exit code $status" >&2
    return "$status"
  fi
}

if [[ "$target" == "installer" ]]; then
  python3 -m PyInstaller \
    --onefile \
    --windowed \
    --noconfirm \
    --distpath . \
    --workpath "$PYINSTALLER_WORKPATH" \
    --specpath "$PYINSTALLER_WORKPATH" \
    --name main.bin \
    --hidden-import vdf \
    main.py
  chmod +x main.bin
  verify_i386 main.bin
  smoke_test ./main.bin
else
  python3 -m PyInstaller \
    --onefile \
    --windowed \
    --noconfirm \
    --distpath . \
    --workpath "$PYINSTALLER_WORKPATH" \
    --specpath "$PYINSTALLER_WORKPATH" \
    --name uninstall-linux-x86.bin \
    uninstaller.py
  chmod +x uninstall-linux-x86.bin
  verify_i386 uninstall-linux-x86.bin
  smoke_test ./uninstall-linux-x86.bin
fi
