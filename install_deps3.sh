#!/bin/bash
# Install dependencies using Tsinghua PyPI mirror

set -e

SITE_PACKAGES="/Users/admin/Desktop/myapps/any-auto-register/.venv/lib/python3.13/site-packages"
PYTHON="/Users/admin/Desktop/myapps/any-auto-register/.venv/bin/python"
TEMP_DIR="/tmp/wheels_$$"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

mkdir -p "$TEMP_DIR"

echo "Installing dependencies from Tsinghua mirror..."
echo ""

# Function to install a package
install_pkg() {
    local pkg="$1"
    local check="${2:-$1}"
    local check_underscore="${check//-/_}"

    # Check if already installed
    if ls "$SITE_PACKAGES"/${check_underscore}-*.dist-info 1> /dev/null 2>&1; then
        echo "⊘ $pkg already installed"
        return 0
    fi

    echo -n "Installing $pkg... "

    # Fetch package page from simple API
    local html_file="$TEMP_DIR/${pkg}.html"
    curl -sL --connect-timeout 10 "$MIRROR/$pkg/" -o "$html_file" 2>/dev/null || {
        echo "✗ fetch failed"
        return 1
    }

    # Extract latest wheel URL using venv python
    local wheel_url=$("$PYTHON" << EOF
import re
import sys

try:
    with open('$html_file') as f:
        html = f.read()

    # Find all wheel links
    wheels = re.findall(r'href="([^"]+\.whl)[^"]*"', html)

    if not wheels:
        sys.exit(1)

    # Prefer py3-none-any or py3-none-macosx or cp313-macosx-arm64 or abi3-macosx-arm64
    for w in wheels:
        if 'py3-none-any' in w:
            # Convert relative URL to absolute
            if w.startswith('../../'):
                w = 'https://pypi.tuna.tsinghua.edu.cn/' + w[6:]
            print(w)
            sys.exit(0)

    # Try py3-none-macosx (universal2 or arm64)
    for w in wheels:
        if 'py3-none-macosx' in w and ('arm64' in w or 'universal2' in w):
            if w.startswith('../../'):
                w = 'https://pypi.tuna.tsinghua.edu.cn/' + w[6:]
            print(w)
            sys.exit(0)

    for w in wheels:
        if 'cp313' in w and 'macosx' in w and ('arm64' in w or 'universal2' in w) and 'cp313t' not in w:
            if w.startswith('../../'):
                w = 'https://pypi.tuna.tsinghua.edu.cn/' + w[6:]
            print(w)
            sys.exit(0)

    # Try abi3 wheels (compatible with multiple Python versions)
    for w in wheels:
        if 'abi3' in w and 'macosx' in w and ('arm64' in w or 'universal2' in w) and 'abi3t' not in w:
            if w.startswith('../../'):
                w = 'https://pypi.tuna.tsinghua.edu.cn/' + w[6:]
            print(w)
            sys.exit(0)

    # Fallback to any wheel
    for w in wheels:
        if 'none-any' in w:
            if w.startswith('../../'):
                w = 'https://pypi.tuna.tsinghua.edu.cn/' + w[6:]
            print(w)
            sys.exit(0)

    sys.exit(1)
except Exception as e:
    sys.exit(1)
EOF
)

    if [ -z "$wheel_url" ]; then
        echo "✗ no compatible wheel"
        return 1
    fi

    # Download wheel
    local wheel_file="$TEMP_DIR/$(basename "$wheel_url")"
    curl -sL --connect-timeout 10 "$wheel_url" -o "$wheel_file" 2>/dev/null || {
        echo "✗ download failed"
        return 1
    }

    # Extract to site-packages
    "$PYTHON" -c "
import zipfile
with zipfile.ZipFile('$wheel_file', 'r') as z:
    z.extractall('$SITE_PACKAGES')
" 2>/dev/null || {
        echo "✗ extract failed"
        return 1
    }

    echo "✓"
    return 0
}

# Install in dependency order
install_pkg "typing_extensions" "typing_extensions"
install_pkg "annotated-types" "annotated_types"
install_pkg "pydantic-core" "pydantic_core"
install_pkg "pydantic" "pydantic"
install_pkg "sqlalchemy" "sqlalchemy"
install_pkg "sqlmodel" "sqlmodel"
install_pkg "idna" "idna"
install_pkg "certifi" "certifi"
install_pkg "charset-normalizer" "charset_normalizer"
install_pkg "urllib3" "urllib3"
install_pkg "requests" "requests"
install_pkg "httpx" "httpx"
install_pkg "anyio" "anyio"
install_pkg "sniffio" "sniffio"
install_pkg "aiofiles" "aiofiles"
install_pkg "markdown-it-py" "markdown_it_py"
install_pkg "pygments" "pygments"
install_pkg "rich" "rich"
install_pkg "click" "click"
install_pkg "itsdangerous" "itsdangerous"
install_pkg "jinja2" "jinja2"
install_pkg "markupsafe" "markupsafe"
install_pkg "werkzeug" "werkzeug"
install_pkg "blinker" "blinker"
install_pkg "h11" "h11"
install_pkg "hypercorn" "hypercorn"
install_pkg "quart" "quart"
install_pkg "cryptography" "cryptography"
install_pkg "jwcrypto" "jwcrypto"
install_pkg "cbor2" "cbor2"
install_pkg "greenlet" "greenlet"
install_pkg "playwright" "playwright"
install_pkg "patchright" "patchright"
install_pkg "camoufox" "camoufox"
install_pkg "curl-cffi" "curl_cffi"
install_pkg "pyinstaller" "pyinstaller"
install_pkg "iniconfig" "iniconfig"
install_pkg "pluggy" "pluggy"
install_pkg "pytest" "pytest"

echo ""
echo "=================================================="
echo "Done!"
echo "=================================================="

# Cleanup
rm -rf "$TEMP_DIR"
