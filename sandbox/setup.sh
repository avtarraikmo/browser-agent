#!/usr/bin/env bash
# Baked once by `mda deploy` / `mda dev`; new threads clone the resulting snapshot.
# Installs Playwright and Chromium (with its system libraries) for browsing from
# the sandbox's `execute` tool.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
# Keep browser binaries in a shared location so every user of the sandbox finds them.
export PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

if ! command -v pip3 >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends python3 python3-pip
fi

# --break-system-packages: Debian/Ubuntu images mark the system Python as externally managed.
pip3 install --break-system-packages playwright
playwright install --with-deps chromium

echo "export PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}" > /etc/profile.d/playwright.sh
chmod -R a+rX "${PLAYWRIGHT_BROWSERS_PATH}"

# `execute` shells are non-login, so profile.d is never sourced and Playwright
# looks in the default cache, not /opt. Link it there so launch works with no env var.
mkdir -p /root/.cache
ln -sfn "${PLAYWRIGHT_BROWSERS_PATH}" /root/.cache/ms-playwright

# Install the browser_cli.py CLI the agent calls via `execute`.
# Copies everything in sandbox/workspace/ (next to this script) into /workspace.
mkdir -p /workspace
cp -r "$(dirname "$0")/workspace/." /workspace/
chmod a+rx /workspace/browser_cli.py

# Fail the bake now if the script or Playwright import is broken.
python3 /workspace/browser_cli.py --help >/dev/null
