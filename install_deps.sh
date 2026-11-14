#!/bin/bash
# Install dependencies by downloading wheels with curl and extracting with Python
# Bypasses pip and Python's SSL issues

set -e

SITE_PACKAGES="/Users/admin/Desktop/myapps/any-auto-register/.venv/lib/python3.13/site-packages"
PYTHON="/Users/admin/Desktop/myapps/any-auto-register/.venv/bin/python"
TEMP_DIR="/tmp/wheels_$$"

mkdir -p "$TEMP_DIR"

echo "Installing dependencies to: $SITE_PACKAGES"
echo ""

# Function to download and install a package
install_wheel() {
    local package_name="$1"
    local check_name="${2:-$1}"

    # Check if already installed
    if ls "$SITE_PACKAGES"/${check_name//-/_}-*.dist-info 1> /dev/null 2>&1; then
        echo "⊘ $package_name already installed"
        return 0
    fi

    echo "Installing $package_name..."

    # Get package info from PyPI using curl
    local json_file="$TEMP_DIR/${package_name}.json"
    if ! curl -sL --connect-timeout 10 "https://pypi.org/pypi/$package_name/json" -o "$json_file" 2>/dev/null; then
        echo "  ✗ Failed to fetch info for $package_name"
        return 1
    fi

    # Extract latest version
    local version=$(python3 -c "import json; print(json.load(open('$json_file'))['info']['version'])" 2>/dev/null)
    if [ -z "$version" ]; then
        echo "  ✗ Failed to parse version for $package_name"
        return 1
    fi

    # Find compatible wheel URL
    local wheel_url=$(python3 << EOF
import json
import sys

with open('$json_file') as f:
    data = json.load(f)

releases = data.get('releases', {}).get('$version', [])

# Prefer pure Python wheels or macOS arm64 wheels
for release in releases:
    filename = release.get('filename', '')
    if not filename.endswith('.whl'):
        continue
    # Check for compatible tags
    if 'py3-none-any' in filename or 'cp313-none-macosx' in filename and 'arm64' in filename:
        print(release['url'])
        sys.exit(0)

# Fallback to any wheel
for release in releases:
    filename = release.get('filename', '')
    if filename.endswith('.whl') and 'none-any' in filename:
        print(release['url'])
        sys.exit(0)

sys.exit(1)
EOF
)

    if [ -z "$wheel_url" ]; then
        echo "  ✗ No compatible wheel found for $package_name"
        return 1
    fi

    # Extract filename from URL
    local wheel_filename=$(basename "$wheel_url")
    local wheel_path="$TEMP_DIR/$wheel_filename"

    # Download wheel
    if ! curl -sL --connect-timeout 10 "$wheel_url" -o "$wheel_path" 2>/dev/null; then
        echo "  ✗ Failed to download $wheel_filename"
        return 1
    fi

    # Extract wheel to site-packages
    if ! "$PYTHON" -c "
import zipfile
import sys
try:
    with zipfile.ZipFile('$wheel_path', 'r') as z:
        z.extractall('$SITE_PACKAGES')
    print('  ✓ Installed $wheel_filename')
except Exception as e:
    print(f'  ✗ Failed to extract: {e}')
    sys.exit(1)
" 2>&1; then
        return 1
    fi

    return 0
}

# Install packages in dependency order
install_wheel "typing_extensions" "typing_extensions" || true
install_wheel "annotated-types" "annotated_types" || true
install_wheel "pydantic-core" "pydantic_core" || true
install_wheel "pydantic" "pydantic" || true
install_wheel "sqlalchemy" "sqlalchemy" || true
install_wheel "sqlmodel" "sqlmodel" || true
install_wheel "requests" "requests" || true
install_wheel "httpx" "httpx" || true
install_wheel "aiofiles" "aiofiles" || true
install_wheel "rich" "rich" || true
install_wheel "markdown-it-py" "markdown_it_py" || true
install_wheel "pygments" "pygments" || true
install_wheel "quart" "quart" || true
install_wheel "jwcrypto" "jwcrypto" || true
install_wheel "cbor2" "cbor2" || true
install_wheel "playwright" "playwright" || true
install_wheel "patchright" "patchright" || true
install_wheel "camoufox" "camoufox" || true
install_wheel "curl-cffi" "curl_cffi" || true
install_wheel "pyinstaller" "pyinstaller" || true
install_wheel "pytest" "pytest" || true

echo ""
echo "=================================================="
echo "Installation complete!"
echo "=================================================="

# Cleanup
rm -rf "$TEMP_DIR"
