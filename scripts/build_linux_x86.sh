#!/bin/bash
set -euo pipefail

target=${1:-}
if [[ "$target" != "installer" && "$target" != "uninstaller" ]]; then
  echo "Usage: $0 installer|uninstaller" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
PIP_CACHE_ROOT=${PIP_CACHE_DIR:-/pip-cache}
export PIP_CACHE_DIR=$PIP_CACHE_ROOT/http
export PIP_WHEEL_DIR=${PIP_WHEEL_DIR:-$PIP_CACHE_ROOT/wheels}
export PYINSTALLER_WORKPATH=${PYINSTALLER_WORKPATH:-/pyinstaller-work/$target}
mkdir -p "$PIP_CACHE_DIR" "$PIP_WHEEL_DIR" "$PYINSTALLER_WORKPATH"

make_caches_archivable() {
  chmod -R a+rX "$PIP_CACHE_ROOT" "$PYINSTALLER_WORKPATH" 2>/dev/null || true
}
trap make_caches_archivable EXIT

# Debian bullseye is the last release shipping the 32-bit PySide2 packages this
# build needs, and bullseye has left security support. Its live suites are no
# longer installable: the mirror still advertises bullseye-security while its
# pool files are gone, and the plain archive only carries the older point
# releases, which the security versions preinstalled in this image cannot be
# completed from. The image records the dated snapshots it was built from, and
# those still serve every version the image and the build need, so install from
# them; set DEBIAN_SNAPSHOT/DEBIAN_SNAPSHOT_STAMP to override, which also
# serves as the fallback for images without that record.
SNAPSHOT_BASE_DEFAULT=http://snapshot.debian.org/archive
SNAPSHOT_STAMP_DEFAULT=20260824T000000Z

configure_apt_sources() {
  local recorded="" base stamp
  base=${DEBIAN_SNAPSHOT:-$SNAPSHOT_BASE_DEFAULT}
  stamp=${DEBIAN_SNAPSHOT_STAMP:-$SNAPSHOT_STAMP_DEFAULT}
  mkdir -p /etc/apt/sources.list.d /etc/apt/apt.conf.d
  rm -rf /var/lib/apt/lists/*
  rm -f /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources
  if [[ -z "${DEBIAN_SNAPSHOT:-}${DEBIAN_SNAPSHOT_STAMP:-}" ]]; then
    recorded=$(sed -n \
      's|^# \(deb http://snapshot\.debian\.org/archive/[^ ]* [a-z-]* main\)$|\1|p' \
      /etc/apt/sources.list)
  fi
  if [[ -n "$recorded" ]]; then
    printf '%s\n' "$recorded" > /etc/apt/sources.list
  else
    cat > /etc/apt/sources.list <<CONF
deb $base/debian/$stamp bullseye main
deb $base/debian/$stamp bullseye-updates main
deb $base/debian-security/$stamp bullseye-security main
CONF
  fi
  # Snapshot Release files are expired by design, and their host occasionally
  # answers slowly, so relax the date check and retry transient failures.
  printf 'Acquire::Check-Valid-Until "false";\nAcquire::Retries "3";\n' \
    > /etc/apt/apt.conf.d/99debian-snapshot
}
configure_apt_sources

BUILD_PACKAGES=(
  binutils build-essential ca-certificates file patchelf
  python3 python3-dev python3-pip
  python3-pyside2.qtcore python3-pyside2.qtgui python3-pyside2.qtwidgets
  libegl1 libgl1 libopengl0 libxkbcommon0 libxkbcommon-x11-0
  libdbus-1-3 libxcb1 libxcb-xinerama0 libxcb-icccm4 libxcb-image0
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0
  libxcb-xfixes0 libxcb-xkb1
)

# The snapshot host also answers with occasional transient 5xx responses, and
# apt keeps its partial downloads, so retry whole transactions rather than
# failing the build on the first hiccup.
apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if "$@"; then
      return 0
    fi
    echo "apt command failed (attempt $attempt): $*" >&2
    sleep 10
  done
  return 1
}

apt_retry apt-get update -qq
apt_retry apt-get install -y --no-install-recommends "${BUILD_PACKAGES[@]}"

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
  timeout 20s env \
    QT_QPA_PLATFORM=offscreen \
    UNIVERSAL_INSTALLER_SMOKE_TEST=1 \
    UNIVERSAL_INSTALLER_SMOKE_REPORT="${SMOKE_REPORT_PATH:-smoke-report-$target.json}" \
    "$executable" || status=$?
  if [[ "$status" -ne 0 && "$status" -ne 124 ]]; then
    echo "Linux binary smoke test failed with exit code $status" >&2
    return "$status"
  fi
}

if [[ "$target" == "installer" ]]; then
  python3 scripts/run_linux_pyinstaller.py \
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
  python3 scripts/run_linux_pyinstaller.py \
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
