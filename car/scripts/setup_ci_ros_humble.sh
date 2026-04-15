#!/usr/bin/env bash
set -euo pipefail

if command -v ros2 >/dev/null 2>&1 && command -v colcon >/dev/null 2>&1; then
  echo '[ci-ros] ros2 and colcon already available; skipping installation'
  ros2 --version || true
  colcon --version || true
  exit 0
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo '[ERR] sudo is required to install ROS 2 Humble on CI runners' >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends curl gnupg2 lsb-release software-properties-common

if [[ ! -f /etc/apt/keyrings/ros-archive-keyring.gpg ]]; then
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | sudo gpg --dearmor -o /etc/apt/keyrings/ros-archive-keyring.gpg
fi

ubuntu_codename="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-jammy}")"
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu ${ubuntu_codename} main" | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ros-humble-ros-base \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  python3-argcomplete

if command -v rosdep >/dev/null 2>&1; then
  sudo rosdep init 2>/dev/null || true
  rosdep update || true
fi

source /opt/ros/humble/setup.bash
ros2 --version
colcon --version

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo 'RELEASE_GATE_ROS_SETUP_BASH=/opt/ros/humble/setup.bash' >> "$GITHUB_ENV"
fi
