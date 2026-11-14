#!/usr/bin/env python3
"""
Install dependencies from PyPI by downloading and extracting wheels directly.
Bypasses pip to work around Python 3.13.16 + macOS 26 expat compatibility issues.
"""
import json
import os
import site
import sys
import urllib.request
import zipfile
from pathlib import Path

SITE_PACKAGES = Path(site.getsitepackages()[0])
PYTHON_TAG = f"cp{sys.version_info.major}{sys.version_info.minor}"
PLATFORM_TAGS = ["py3", "py3-none-any"]

# Add platform-specific tags for macOS
if sys.platform == "darwin":
    import platform
    arch = platform.machine()
    if arch == "arm64":
        PLATFORM_TAGS.extend([
            f"{PYTHON_TAG}-none-macosx_11_0_arm64",
            f"{PYTHON_TAG}-none-macosx_12_0_arm64",
            f"{PYTHON_TAG}-none-macosx_13_0_arm64",
            f"{PYTHON_TAG}-none-macosx_14_0_arm64",
            f"{PYTHON_TAG}-none-macosx_15_0_arm64",
        ])
    else:
        PLATFORM_TAGS.extend([
            f"{PYTHON_TAG}-none-macosx_10_9_x86_64",
            f"{PYTHON_TAG}-none-macosx_11_0_x86_64",
        ])

def get_pypi_info(package_name):
    """Get package info from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ✗ Failed to fetch {package_name}: {e}")
        return None

def find_compatible_wheel(package_name, version):
    """Find a compatible wheel file for this Python/platform."""
    info = get_pypi_info(package_name)
    if not info:
        return None

    if version == "latest":
        version = info["info"]["version"]

    releases = info.get("releases", {}).get(version, [])

    # Try to find a compatible wheel
    for release in releases:
        filename = release.get("filename", "")
        if not filename.endswith(".whl"):
            continue

        # Check if this wheel is compatible
        for tag in PLATFORM_TAGS:
            if tag in filename:
                return release["url"], filename

    # Fallback to pure Python wheel
    for release in releases:
        filename = release.get("filename", "")
        if filename.endswith(".whl") and "none-any" in filename:
            return release["url"], filename

    return None

def download_and_extract(url, filename):
    """Download a wheel file and extract it to site-packages."""
    print(f"  Downloading {filename}...")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()

        # Save to temp file
        temp_path = Path("/tmp") / filename
        with open(temp_path, "wb") as f:
            f.write(data)

        # Extract to site-packages
        with zipfile.ZipFile(temp_path, "r") as zip_ref:
            zip_ref.extractall(SITE_PACKAGES)

        print(f"  ✓ Installed {filename}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to install {filename}: {e}")
        return False

def install_package(package_spec):
    """Install a single package from a spec like 'package>=1.0.0'."""
    # Parse package name and version constraint
    if ">=" in package_spec:
        package_name, version = package_spec.split(">=", 1)
        version = "latest"
    elif "==" in package_spec:
        package_name, version = package_spec.split("==", 1)
    else:
        package_name = package_spec
        version = "latest"

    package_name = package_name.strip()

    # Skip if already installed
    installed = list(SITE_PACKAGES.glob(f"{package_name.replace('-', '_')}-*.dist-info"))
    if installed:
        print(f"  ⊘ {package_name} already installed")
        return True

    print(f"Installing {package_name}...")

    # Find compatible wheel
    wheel_info = find_compatible_wheel(package_name, version)
    if not wheel_info:
        print(f"  ✗ No compatible wheel found for {package_name}")
        return False

    url, filename = wheel_info

    # Download and extract
    return download_and_extract(url, filename)

def main():
    requirements_file = Path(__file__).parent / "requirements.txt"

    if not requirements_file.exists():
        print("✗ requirements.txt not found")
        sys.exit(1)

    print(f"Installing dependencies to: {SITE_PACKAGES}")
    print(f"Python: {sys.version}")
    print()

    # Read requirements
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # Install each package
    success_count = 0
    fail_count = 0

    for req in requirements:
        if install_package(req):
            success_count += 1
        else:
            fail_count += 1
        print()

    print("=" * 60)
    print(f"✓ Installed: {success_count}")
    if fail_count > 0:
        print(f"✗ Failed: {fail_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
