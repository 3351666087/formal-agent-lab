# P1-001 environment check

captured_at: 2026-09-26T14:03:48Z

## repository
- remote: https://github.com/3351666087/formal-agent-lab.git
- branch: main, commits: 0 (empty repository at start)
- uncommitted user changes at start: none (fresh clone)

## host (dev VM)
- os: Ubuntu 24.04.4 LTS, kernel 6.8.0-117-generic, arch aarch64
- cpus: 4, memory: 5910 MiB, root disk free: 17G, docker data disk free: 28G
- docker: 29.5.2 (Ubuntu 24.04.4 LTS aarch64), compose 5.1.4
- virtualization: Colima (Lima vz) on macOS Apple M4 host, Rosetta binfmt for linux/amd64 images

## toolchain (scripts/bootstrap-dev-vm.sh)
- uv --version: uv 0.12.19 (aarch64-unknown-linux-gnu)
- node --version: v24.21.0
- pnpm --version: 12.6.0
- helm version --short: v4.3.0+gbec5b06
- temporal --version: temporal version 1.9.1 (Server 1.32.0, UI 2.54.1)
- python3 --version: Python 3.12.3
- make --version: GNU Make 4.3
