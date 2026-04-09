#!/usr/bin/env bash
set -euo pipefail

require_option_value() {
  local option_name="$1"
  local option_value="${2:-}"
  if [[ -z "$option_value" || "$option_value" == --* ]]; then
    echo "missing value for $option_name" >&2
    return 2
  fi
}

build_source_pythonpath() {
  local src_dir="$1"
  local -a package_paths=()
  while IFS= read -r -d '' setup_file; do
    package_paths+=("$(dirname "$setup_file")")
  done < <(find "$src_dir" -mindepth 2 -maxdepth 2 -name setup.py -print0 | sort -z)
  local joined=""
  local item=""
  for item in "${package_paths[@]}"; do
    joined+="${joined:+:}${item}"
  done
  printf '%s' "$joined"
}

run_surface_preflight_gate() {
  local workspace_root="$1"
  local surface_name="$2"
  local profile_name="$3"
  local config_path="$4"
  local report_dir="$5"
  local source_pythonpath=""
  local -a args=(--profile "$profile_name" --surface "$surface_name" --report-dir "$report_dir" --startup-gate)
  if [[ -n "$config_path" ]]; then
    args+=(--config-path "$config_path")
  fi
  source_pythonpath="$(build_source_pythonpath "$workspace_root/src")"
  if [[ -n "$source_pythonpath" ]]; then
    PYTHONPATH="$source_pythonpath${PYTHONPATH:+:$PYTHONPATH}" python3 -m robot_bringup.preflight "${args[@]}"
  else
    python3 -m robot_bringup.preflight "${args[@]}"
  fi
}

ensure_internal_command_runtime() {
  local runtime_root="${INSPECTION_ROBOT_RUNTIME_DIR:-/tmp/inspection_robot}"
  mkdir -p "$runtime_root"
  chmod 700 "$runtime_root"
  if [[ -z "${ROBOT_INTERNAL_COMMAND_RUNTIME_DIR:-}" ]]; then
    ROBOT_INTERNAL_COMMAND_RUNTIME_DIR="$(mktemp -d "$runtime_root/internal-command.XXXXXX")"
    export ROBOT_INTERNAL_COMMAND_RUNTIME_DIR
  fi
  chmod 700 "$ROBOT_INTERNAL_COMMAND_RUNTIME_DIR"
  export ROBOT_INTERNAL_COMMAND_SOCKET_PATH="${ROBOT_INTERNAL_COMMAND_SOCKET_PATH:-$ROBOT_INTERNAL_COMMAND_RUNTIME_DIR/bridge_internal_command.sock}"
  if [[ -z "${ROBOT_INTERNAL_COMMAND_AUTH_TOKEN:-}" ]]; then
    ROBOT_INTERNAL_COMMAND_AUTH_TOKEN="$(python3 - <<'PY2'
import secrets
print(secrets.token_urlsafe(32))
PY2
)"
    export ROBOT_INTERNAL_COMMAND_AUTH_TOKEN
  fi
  if [[ -z "${ROBOT_OPERATOR_TOKEN:-}" ]]; then
    ROBOT_OPERATOR_TOKEN="$(python3 - <<'PY3'
import secrets
print(secrets.token_urlsafe(24))
PY3
)"
    export ROBOT_OPERATOR_TOKEN
  fi
}

materialize_surface_config() {
  local ubuntu_root="$1"
  local surface_name="$2"
  local profile_name="$3"
  local config_path="$4"
  local output_path="$5"
  local -a args=(--profile "$profile_name" --surface "$surface_name" --output "$output_path" --emit-shell)
  if [[ -n "$config_path" ]]; then
    args+=(--config-path "$config_path")
  fi
  ensure_internal_command_runtime
  python3 "$ubuntu_root/scripts/resolve_runtime_surface_config.py" "${args[@]}" >/dev/null
  # shellcheck disable=SC1090
  source "$output_path"
}

profile_allows_implicit_build() {
  local profile_name="$1"
  case "$profile_name" in
    minimal|mock|dev)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

workspace_install_status() {
  local workspace_root="$1"
  local install_setup="$workspace_root/install/setup.bash"
  local install_local="$workspace_root/install/local_setup.bash"
  local install_ament_index="$workspace_root/install/share/ament_index/resource_index/packages"
  if [[ ! -f "$install_setup" ]]; then
    printf 'missing'
    return 0
  fi
  if [[ -f "$install_local" || -d "$install_ament_index" ]]; then
    printf 'valid'
    return 0
  fi
  if grep -Eq '^[[:space:]]*[^#[:space:]]' "$install_setup"; then
    printf 'valid_minimal'
    return 0
  fi
  printf 'stub'
}

source_workspace_install() {
  local install_setup="$1"
  # shellcheck disable=SC1090
  source "$install_setup"
}

ensure_workspace_install_ready() {
  # Ensure the workspace install tree is semantically usable before launch.
  # A placeholder setup.bash with no effective exports is treated as a stub and
  # will not be accepted as a valid install tree.
  local workspace_root="$1"
  local profile_name="$2"
  local allow_build_if_needed="$3"
  local install_setup="$workspace_root/install/setup.bash"
  local status=""
  status="$(workspace_install_status "$workspace_root")"
  case "$status" in
    valid|valid_minimal)
      source_workspace_install "$install_setup"
      return 0
      ;;
    stub)
      if [[ "$allow_build_if_needed" -ne 1 ]]; then
        echo "detected stub $install_setup; build the workspace first or enable --build-if-needed" >&2
        return 1
      fi
      echo "[runtime] detected stub install tree; rebuilding workspace explicitly..." >&2
      ;;
    missing)
      if [[ "$allow_build_if_needed" -ne 1 ]]; then
        echo "missing $install_setup; build the workspace first or enable --build-if-needed" >&2
        return 1
      fi
      echo "[runtime] install/setup.bash not found; building source workspace explicitly..." >&2
      ;;
    *)
      echo "unrecognized install tree status: $status" >&2
      return 1
      ;;
  esac
  colcon build --symlink-install
  status="$(workspace_install_status "$workspace_root")"
  if [[ "$status" != "valid" && "$status" != "valid_minimal" ]]; then
    echo "workspace build completed but install tree status is still $status" >&2
    return 1
  fi
  source_workspace_install "$install_setup"
}
