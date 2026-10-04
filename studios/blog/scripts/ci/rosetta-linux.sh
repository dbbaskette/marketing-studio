#!/usr/bin/env bash
# Guest-only setup, following Apple's Linux Rosetta binfmt instructions.
set -euo pipefail
sudo -n mkdir -p /mnt/rosetta
mountpoint -q /mnt/rosetta || sudo -n mount -t virtiofs rosetta /mnt/rosetta
[[ -x /mnt/rosetta/rosetta ]] || { echo 'Tart must attach --rosetta=rosetta' >&2; exit 1; }
sudo -n dpkg --add-architecture amd64
# ARM packages continue to use ports; AMD64 packages use the archive mirrors.
sudo -n sed -i '/^Architectures:/d; /^Types: deb/a Architectures: arm64' /etc/apt/sources.list.d/ubuntu.sources
printf '%s\n' \
  'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu noble main universe' \
  'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu noble-updates main universe' \
  'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://security.ubuntu.com/ubuntu noble-security main universe' \
  | sudo -n tee /etc/apt/sources.list.d/ci-amd64.list >/dev/null
sudo -n env DEBIAN_FRONTEND=noninteractive apt-get update
sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y binfmt-support python3-venv libc6:amd64 libgcc-s1:amd64 zlib1g:amd64 libstdc++6:amd64
sudo -n /usr/sbin/update-binfmts --install rosetta /mnt/rosetta/rosetta \
  --magic '\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00' \
  --mask '\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff' \
  --credentials yes --preserve yes --fix-binary yes
