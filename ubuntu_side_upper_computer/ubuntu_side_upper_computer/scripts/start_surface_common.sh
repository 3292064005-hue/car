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

ensure_workspace_install_ready() {
  local workspace_root="$1"
  local profile_name="$2"
  local allow_build_if_needed="$3"
  local install_setup="$workspace_root/install/setup.bash"
  if [[ -f "$install_setup" ]]; then
    # shellcheck disable=SC1090
    source "$install_setup"
    return 0
  fi
  if [[ "$allow_build_if_needed" -ne 1 ]]; then
    echo "missing $install_setup; build the workspace first or enable --build-if-needed" >&2
    return 1
  fi
  echo "[runtime] install/setup.bash not found; building source workspace explicitly..."
  colcon build --symlink-install
  if [[ ! -f "$install_setup" ]]; then
    echo "workspace build completed but $install_setup is still missing" >&2
    return 1
  fi
  # shellcheck disable=SC1090
  source "$install_setup"
}
