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

# Run the shared preflight gate for one surface.
# Args: workspace_root surface_name profile_name config_path report_dir
# Returns: 0 on success, non-zero on blocking preflight failure.
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

_generate_runtime_token() {
  local random_bytes="${1:-32}"
  head -c "$random_bytes" /dev/urandom | base64 | tr -d '\n=' | tr '+/' '-_' | cut -c1-64
}

_runtime_bootstrap_mode() {
  local explicit_mode="${ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE:-auto}"
  case "$explicit_mode" in
    auto)
      printf '%s' "${ROBOT_EFFECTIVE_OPERATOR_SESSION_BOOTSTRAP_MODE:-external}"
      ;;
    disabled|external|required)
      printf '%s' "$explicit_mode"
      ;;
    *)
      echo "unsupported ROBOT_OPERATOR_SESSION_BOOTSTRAP_MODE: $explicit_mode" >&2
      return 2
      ;;
  esac
}

_runtime_scope_id() {
  local profile_name="${ROBOT_EFFECTIVE_PROFILE:-unknown}"
  local config_root="${ROBOT_EFFECTIVE_CONFIG_ROOT:-unknown}"
  local checksum=""
  checksum="$(printf '%s' "${profile_name}|${config_root}" | cksum | awk '{print $1}')"
  printf '%s' "${profile_name}-${checksum}"
}

# Materialize deterministic runtime bootstrap directories and shared secrets.
# Args: none (consumes ROBOT_EFFECTIVE_* exports emitted by the pure resolver)
# Exports: ROBOT_INTERNAL_COMMAND_RUNTIME_DIR / SOCKET_PATH / AUTH_TOKEN / OPERATOR_TOKEN
# Boundary behavior: token files are reused across separate frontend/backend shells
# when they target the same profile + config root scope.
ensure_internal_command_runtime() {
  local runtime_root="${INSPECTION_ROBOT_RUNTIME_DIR:-/tmp/inspection_robot}"
  local scope_id=""
  local runtime_dir=""
  local socket_path=""
  local internal_token_file=""
  local operator_token_file=""
  mkdir -p "$runtime_root"
  chmod 700 "$runtime_root"
  scope_id="$(_runtime_scope_id)"
  runtime_dir="${ROBOT_INTERNAL_COMMAND_RUNTIME_DIR:-$runtime_root/runtime-$scope_id}"
  mkdir -p "$runtime_dir"
  chmod 700 "$runtime_dir"
  internal_token_file="$runtime_dir/internal_command_auth.token"
  operator_token_file="$runtime_dir/operator_session.token"
  socket_path="${ROBOT_INTERNAL_COMMAND_SOCKET_PATH:-$runtime_dir/bridge_internal_command.sock}"

  if [[ -z "${ROBOT_INTERNAL_COMMAND_AUTH_TOKEN:-}" ]]; then
    if [[ -f "$internal_token_file" ]]; then
      ROBOT_INTERNAL_COMMAND_AUTH_TOKEN="$(<"$internal_token_file")"
    else
      ROBOT_INTERNAL_COMMAND_AUTH_TOKEN="$(_generate_runtime_token 32)"
      printf '%s' "$ROBOT_INTERNAL_COMMAND_AUTH_TOKEN" > "$internal_token_file"
      chmod 600 "$internal_token_file"
    fi
  fi
  if [[ -z "${ROBOT_OPERATOR_TOKEN:-}" ]]; then
    if [[ -f "$operator_token_file" ]]; then
      ROBOT_OPERATOR_TOKEN="$(<"$operator_token_file")"
    else
      ROBOT_OPERATOR_TOKEN="$(_generate_runtime_token 24)"
      printf '%s' "$ROBOT_OPERATOR_TOKEN" > "$operator_token_file"
      chmod 600 "$operator_token_file"
    fi
  fi

  export ROBOT_INTERNAL_COMMAND_RUNTIME_DIR="$runtime_dir"
  export ROBOT_INTERNAL_COMMAND_SOCKET_PATH="$socket_path"
  export ROBOT_INTERNAL_COMMAND_AUTH_TOKEN
  export ROBOT_OPERATOR_TOKEN
}

_append_export_line() {
  local output_path="$1"
  local key="$2"
  local value="$3"
  printf 'export %s=%q\n' "$key" "$value" >> "$output_path"
}

# Finalize runtime bootstrap after the pure resolver has emitted its contract.
# Args: surface_name output_path
# Returns: 0 on success. Non-zero when required session bootstrap cannot be satisfied.
# Boundary behavior: frontend local-auto bootstrap injects browser session env only
# for loopback host-harness surfaces; remote surfaces stay token-free by default.
bootstrap_surface_runtime() {
  local surface_name="$1"
  local output_path="$2"
  local session_mode=""
  local session_id=""
  session_mode="$(_runtime_bootstrap_mode)"
  ensure_internal_command_runtime

  _append_export_line "$output_path" ROBOT_INTERNAL_COMMAND_RUNTIME_DIR "$ROBOT_INTERNAL_COMMAND_RUNTIME_DIR"
  _append_export_line "$output_path" ROBOT_INTERNAL_COMMAND_SOCKET_PATH "$ROBOT_INTERNAL_COMMAND_SOCKET_PATH"
  _append_export_line "$output_path" ROBOT_INTERNAL_COMMAND_AUTH_TOKEN "$ROBOT_INTERNAL_COMMAND_AUTH_TOKEN"
  _append_export_line "$output_path" ROBOT_OPERATOR_TOKEN "$ROBOT_OPERATOR_TOKEN"

  if [[ "$surface_name" != "frontend" ]]; then
    return 0
  fi

  session_id="${ROBOT_EFFECTIVE_PROFILE:-mock}-frontend"
  case "$session_mode" in
    disabled)
      export VITE_ROBOT_SESSION_MODE="disabled"
      export VITE_ROBOT_SESSION_ROLE=""
      export VITE_ROBOT_SESSION_TOKEN=""
      export VITE_ROBOT_SESSION_ID=""
      ;;
    external)
      export VITE_ROBOT_SESSION_MODE="external"
      export VITE_ROBOT_SESSION_ROLE=""
      export VITE_ROBOT_SESSION_TOKEN=""
      export VITE_ROBOT_SESSION_ID=""
      export ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE=""
      export ROBOT_EFFECTIVE_FRONTEND_SESSION_ID=""
      ;;
    local_auto|required)
      export VITE_ROBOT_SESSION_MODE="$session_mode"
      export VITE_ROBOT_SESSION_ROLE="operator"
      export VITE_ROBOT_SESSION_TOKEN="$ROBOT_OPERATOR_TOKEN"
      export VITE_ROBOT_SESSION_ID="$session_id"
      export ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE="operator"
      export ROBOT_EFFECTIVE_FRONTEND_SESSION_ID="$session_id"
      ;;
    *)
      echo "unsupported runtime session bootstrap mode: $session_mode" >&2
      return 2
      ;;
  esac

  if [[ "$session_mode" == "required" && -z "${VITE_ROBOT_SESSION_TOKEN:-}" ]]; then
    echo "operator session bootstrap is required but no frontend session token is available" >&2
    return 1
  fi

  _append_export_line "$output_path" VITE_ROBOT_SESSION_MODE "${VITE_ROBOT_SESSION_MODE:-}"
  _append_export_line "$output_path" VITE_ROBOT_SESSION_ROLE "${VITE_ROBOT_SESSION_ROLE:-}"
  _append_export_line "$output_path" VITE_ROBOT_SESSION_TOKEN "${VITE_ROBOT_SESSION_TOKEN:-}"
  _append_export_line "$output_path" VITE_ROBOT_SESSION_ID "${VITE_ROBOT_SESSION_ID:-}"
  _append_export_line "$output_path" ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE "${ROBOT_EFFECTIVE_FRONTEND_SESSION_ROLE:-}"
  _append_export_line "$output_path" ROBOT_EFFECTIVE_FRONTEND_SESSION_ID "${ROBOT_EFFECTIVE_FRONTEND_SESSION_ID:-}"
}

# Resolve one surface contract first, then apply runtime bootstrap side effects.
# Args: ubuntu_root surface_name profile_name config_path output_path
# Returns: 0 on success.
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
  bootstrap_surface_runtime "$surface_name" "$output_path"
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

_workspace_install_status_accepted_for_profile() {
  local status="$1"
  local profile_name="$2"
  case "$status" in
    valid)
      return 0
      ;;
    valid_minimal)
      if profile_allows_implicit_build "$profile_name" || [[ "${ROBOT_ALLOW_MINIMAL_INSTALL:-0}" == "1" ]]; then
        return 0
      fi
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

# Ensure the ROS install tree matches the current launch profile's strictness.
# Args: workspace_root profile_name allow_build_if_needed
# Returns: 0 when a usable install tree has been sourced.
# Boundary behavior: production-like profiles reject valid_minimal install trees
# unless ROBOT_ALLOW_MINIMAL_INSTALL=1 or a rebuild path is explicitly allowed.
ensure_workspace_install_ready() {
  local workspace_root="$1"
  local profile_name="$2"
  local allow_build_if_needed="$3"
  local install_setup="$workspace_root/install/setup.bash"
  local status=""
  status="$(workspace_install_status "$workspace_root")"
  if _workspace_install_status_accepted_for_profile "$status" "$profile_name"; then
    source_workspace_install "$install_setup"
    return 0
  fi
  case "$status" in
    valid_minimal)
      if [[ "$allow_build_if_needed" -ne 1 ]]; then
        echo "detected minimal install tree at $install_setup; rebuild the workspace first, enable --build-if-needed, or set ROBOT_ALLOW_MINIMAL_INSTALL=1 for this profile" >&2
        return 1
      fi
      echo "[runtime] detected minimal install tree for profile $profile_name; rebuilding workspace explicitly..." >&2
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
  if ! _workspace_install_status_accepted_for_profile "$status" "$profile_name"; then
    echo "workspace build completed but install tree status is still $status for profile $profile_name" >&2
    return 1
  fi
  source_workspace_install "$install_setup"
}
