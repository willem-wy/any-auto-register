#!/bin/bash
# Install dependencies using curl for downloads and venv python for extraction

set -e

SITE_PACKAGES="/Users/admin/Desktop/myapps/any-auto-register/.venv/lib/python3.13/site-packages"
PYTHON="/Users/admin/Desktop/myapps/any-auto-register/.venv/bin/python"
TEMP_DIR="/tmp/wheels_$$"

mkdir -p "$TEMP_DIR"

echo "Installing dependencies..."
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

    # Download JSON info (use Tsinghua mirror for better connectivity in China)
    local json_file="$TEMP_DIR/${pkg}.json"
    curl -sL --connect-timeout 10 "https://pypi.tuna.tsinghua.edu.cn/pypi/$pkg/json" -o "$json_file" 2>/dev/null || {
        echo "✗ fetch failed"
        return 1
    }

    # Extract wheel URL using venv python
    local wheel_url=$("$PYTHON" << EOF
import json
import sys

try:
    with open('$json_file') as f:
        data = json.load(f)

    version = data['info']['version']
    releases = data.get('releases', {}).get(version, [])

    # Find compatible wheel
    for r in releases:
        fn = r.get('filename', '')
        if fn.endswith('.whl') and ('py3-none-any' in fn or 'cp313-none-macosx' in fn and 'arm64' in fn):
            print(r['url'])
            sys.exit(0)

    # Fallback
    for r in releases:
        fn = r.get('filename', '')
        if fn.endswith('.whl') and 'none-any' in fn:
            print(r['url'])
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
    curl -sL --connect-timeout 10 --proxy http://127.0.0.1:7890 "$wheel_url" -o "$wheel_file" 2>/dev/null || {
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
