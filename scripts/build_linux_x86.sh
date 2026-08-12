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
mkdir -p "$PIP_CACHE_DIR" "$PIP_WHEEL_DIR"
apt-get update -qq
apt-get install -y --no-install-recommends \
  build-essential ca-certificates ccache file patchelf wget \
  python3 python3-dev python3-pip python3-pil \
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

export CCACHE_DIR=${CCACHE_DIR:-/ccache}
export CCACHE_MAXSIZE=${CCACHE_MAXSIZE:-1G}
export PATH="/usr/lib/ccache:$PATH"
mkdir -p "$CCACHE_DIR"
ccache --set-config=max_size="$CCACHE_MAXSIZE"
ccache --zero-stats

verify_i386() {
  file "$1" | tee /dev/stderr | grep -Eq "ELF 32-bit.*Intel 80386"
}

copy_runtime_libraries() {
  local destination=$1
  local libraries=(
    libxkbcommon.so.0 libxkbcommon-x11.so.0 libdbus-1.so.3 libEGL.so.1
    libGL.so.1 libOpenGL.so.0 libGLX.so.0 libGLdispatch.so.0
    libxcb-xinerama.so.0 libxcb-icccm.so.4 libxcb-image.so.0
    libxcb-keysyms.so.1 libxcb-randr.so.0 libxcb-render-util.so.0
    libxcb-shape.so.0 libxcb-xfixes.so.0 libxcb-xkb.so.1 libxcb.so.1
    libX11.so.6 libXext.so.6 libXi.so.6 libXrender.so.1 libXcursor.so.1
    libXfixes.so.3 libXrandr.so.2 libXdamage.so.1 libXcomposite.so.1
    libdrm.so.2 libgbm.so.1
  )
  local library source
  for library in "${libraries[@]}"; do
    source=$(find /usr/lib/i386-linux-gnu -name "$library" -print -quit)
    if [[ -n "$source" ]]; then
      cp -L "$source" "$destination/"
    fi
  done
}

make_icon() {
  local destination=$1
  python3 - "$destination" <<'PY'
from pathlib import Path
import sys
from PIL import Image

destination = Path(sys.argv[1])
image = Image.open("pack/icon.ico")
if getattr(image, "n_frames", 1) > 1:
    image.seek(0)
resampling = getattr(Image, "Resampling", Image)
image.convert("RGBA").resize((256, 256), resampling.LANCZOS).save(
    destination
)
PY
}

build_appimage() {
  local appdir=$1
  local output=$2
  wget -nv -O appimagetool-i686.AppImage \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-i686.AppImage"
  chmod +x appimagetool-i686.AppImage
  APPIMAGE_EXTRACT_AND_RUN=1 ARCH=i686 \
    ./appimagetool-i686.AppImage -v "$appdir" "$output"
  chmod +x "$output"
  verify_i386 "$output"
}

if [[ "$target" == "installer" ]]; then
  python3 -m nuitka \
    --onefile \
    --include-module=vdf \
    --enable-plugin=pyside2 \
    --assume-yes-for-downloads \
    --deployment \
    --output-filename=main.bin \
    main.py
  chmod +x main.bin
  verify_i386 main.bin

  python3 -m nuitka \
    --standalone \
    --include-module=vdf \
    --enable-plugin=pyside2 \
    --assume-yes-for-downloads \
    --deployment \
    --output-dir=appimage-main-build \
    --output-filename=main \
    main.py
  verify_i386 appimage-main-build/main.dist/main

  mkdir -p AppDir/usr/bin AppDir/usr/lib
  cp -a appimage-main-build/main.dist/. AppDir/usr/bin/
  copy_runtime_libraries AppDir/usr/lib
  make_icon AppDir/icon.png
  cp scripts/linux-main.desktop AppDir/main.desktop
  cp scripts/linux-main-apprun AppDir/AppRun
  chmod +x AppDir/AppRun AppDir/usr/bin/main
  build_appimage AppDir main.AppImage
else
  python3 -m nuitka \
    --onefile \
    --enable-plugin=pyside2 \
    --assume-yes-for-downloads \
    --deployment \
    --output-filename=uninstall-linux-x86.bin \
    uninstaller.py
  chmod +x uninstall-linux-x86.bin
  verify_i386 uninstall-linux-x86.bin

  python3 -m nuitka \
    --standalone \
    --enable-plugin=pyside2 \
    --assume-yes-for-downloads \
    --deployment \
    --output-dir=appimage-uninstaller-build \
    --output-filename=uninstaller \
    uninstaller.py
  verify_i386 appimage-uninstaller-build/uninstaller.dist/uninstaller

  mkdir -p UninstallerAppDir/usr/bin UninstallerAppDir/usr/lib
  cp -a appimage-uninstaller-build/uninstaller.dist/. UninstallerAppDir/usr/bin/
  copy_runtime_libraries UninstallerAppDir/usr/lib
  make_icon UninstallerAppDir/icon.png
  cp scripts/linux-uninstaller.desktop UninstallerAppDir/uninstaller.desktop
  cp scripts/linux-uninstaller-apprun UninstallerAppDir/AppRun
  chmod +x UninstallerAppDir/AppRun UninstallerAppDir/usr/bin/uninstaller
  build_appimage UninstallerAppDir uninstall-linux-x86.AppImage
fi

ccache --show-stats
