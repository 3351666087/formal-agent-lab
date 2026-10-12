#!/bin/bash
# 把 Colima 从 x86_64 (QEMU 全模拟) 迁移到 ARM64 Ubuntu (vz + Rosetta)，不带任何代理配置。
set -euo pipefail

BACKUP=/tmp/claude-501/colima-migrate
VOL=996c02607ee6793880da4503fd025159e76034e2282afdb326015d3c924ac613
PATTERN='\.colima/_lima|colima daemon'

# 不让 Colima 把宿主机代理变量写进虚拟机
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy NO_PROXY no_proxy

echo "==> [1/6] 结束旧 x86 虚拟机的残留进程"
pgrep -fl "$PATTERN" || echo "(没有残留进程)"
pkill -f "$PATTERN" || true
for _ in {1..10}; do pgrep -f "$PATTERN" >/dev/null || break; sleep 1; done
pkill -9 -f "$PATTERN" || true

echo "==> [2/6] 删除旧虚拟机的数据盘、网络目录和 x86 配置"
rm -rf ~/.colima/_lima/_disks/colima ~/.colima/_lima/_networks/user-v2 ~/.colima/default

echo "==> [3/6] 创建 ARM64 Ubuntu 虚拟机 (vz + Rosetta + virtiofs)"
colima start --arch aarch64 --vm-type vz --vz-rosetta --mount-type virtiofs --cpu 4 --memory 6 --disk 30

echo "==> [4/6] 验证"
colima list
docker info --format 'OS={{.OperatingSystem}}  Arch={{.Architecture}}  CPUs={{.NCPU}}'
docker info 2>/dev/null | grep -i 'proxy:' || echo "Docker 守护进程: 无代理"
colima ssh -- sh -c 'grep -i proxy /etc/environment || echo "虚拟机 /etc/environment: 无代理"'
docker run --rm ubuntu:24.04 sh -c 'echo "ubuntu 容器: $(uname -m) / $(. /etc/os-release; echo $PRETTY_NAME)"'
echo "Rosetta amd64 容器: $(docker run --rm --platform linux/amd64 alpine:3.21 uname -m)"
docker rmi alpine:3.21 >/dev/null

echo "==> [5/6] 恢复 asimov 镜像和数据卷"
docker load -i "$BACKUP/asimov-images.tar"
docker volume create "$VOL" >/dev/null
docker run --rm -i -v "$VOL":/v ubuntu:24.04 tar -C /v -xzf - < "$BACKUP/vol-$VOL.tgz"
docker run --rm -v "$VOL":/v ubuntu:24.04 ls -la /v

echo "==> [6/6] 清理备份和镜像下载缓存"
du -sh ~/Library/Caches/colima 2>/dev/null || true
rm -rf "$BACKUP" ~/Library/Caches/colima
df -h ~ | tail -1
echo "==> 完成"
