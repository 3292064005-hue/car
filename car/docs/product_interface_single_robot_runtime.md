# Product interface / single-robot runtime alignment

## Scope

This delivery aligns the repository with four confirmed architecture decisions:

1. Hardware runtime semantics are split into three explicit roles: `ros_projection_only`, `ros_soft_driver`, and `verified_board_driver`. The legacy `direct_driver` token remains only as a compatibility alias.
2. Complex patrol execution is a decision-owned single-robot mission catalog with explicit stage admission/executor ownership instead of ad hoc frontend route triggering or auto-completed non-route stages.
3. Fleet / scheduler integration remains disabled at runtime; external schedulers are rejected by policy in this release.
4. The frontend protocol is promoted to a formal product interface exposed by the 9100 API facade.

## Product API

The authoritative product write surface remains the API facade on port 9100.

Formal HTTP endpoints:

- `/api/v1/health`
- `/api/v1/state`
- `/api/v1/runtime`
- `/api/v1/logs`
- `/api/v1/commands`
- `/api/v1/product-interface`
- `/api/v1/missions`

`/api/v1/product-interface` exports the product-facing contract, including command routes, surface registry, mission catalog, and single-robot scheduling policy.

`/api/v1/missions` exports the operator-visible single-robot mission catalog. The frontend patrol page resolves `/api/v1/product-interface` at runtime and then reads `/api/v1/missions` as its authoritative mission source; the generated mission catalog remains bootstrap-only fallback for offline previews.

## Mission catalog

Mission definitions live in `ros2_ws/src/robot_bringup/config/mission_catalog.yaml`.

The frontend submits `missionId`, `routeName`, and `taskProfile` for `start_patrol`. The decision layer remains authoritative for translating that request into mission stages and navigation work. Unsupported stage kinds are rejected at mission-admission time, and `verification` is executed by the decision layer through a stage executor instead of being auto-completed.

## Fleet policy

`fleet_adapter_boundary.py` resolves every scheduler enable request to a rejected runtime activation in this release. The contract remains available so future work can re-enable it without changing external ingress semantics.

## Hardware rollout / rollback

Default hardware config now selects a ROS-owned soft driver boundary with no board-execution claim:

- `compatibility_surface_role: ros_soft_driver`
- `command_transport: direct_driver_loop`
- `transport_authority: ros_process_driver`
- `board_execution_confirmed: false`
- `verification_stage: host_harness_only`

Rollback to pure projection remains config-driven by switching `hardware_interface.yaml` to:

- `compatibility_surface_role: ros_projection_only`
- `command_transport: tcp_json_bridge`
- `transport_authority: external_board_controller`

Promotion to board-execution claim requires explicit verified-board configuration:

- `compatibility_surface_role: verified_board_driver`
- `board_validation_in_repo: true`
- `board_execution_confirmed: true`
- `verification_stage: hardware_in_loop_verified`
- a fresh `verification_artifact_path` bound to the current source/config/protocol identity

Launch, report, runtime-surface resolution, and release checks share the same hardware activation decision object. Host-harness tiers downgrade driver requests to `ros_projection_only`; real-robot tiers may activate `ros_soft_driver` without a board-execution claim; only `verified_board_driver` can expose `ros_runtime_board_execution_confirmed`.

The repository carries explicit `ros2_control` migration artifacts under `robot_description/config/ros2_control.controllers.yaml` and `robot_description/urdf/inspection_robot.ros2_control.xacro` so the standardization target is tied to concrete files rather than prose only. These artifacts are migration anchors, not proof that the current runtime already runs through a `ros2_control` hardware plugin.

## Hardware-in-loop evidence provenance

A verified-board activation artifact is not allowed to create a successful board-execution claim by itself. It must be derived from an execution report that carries source tree identity, bringup config digest, protocol identity, hardware identity, firmware identity, test-runner identity, and raw transcript hashes. Packaging compares those execution-time identities with the current repository/config/protocol reference before allowing a verified-board claim.

If the HIL report is missing, stale, lacks raw transcript hashes, or does not match the current source/config/protocol identity, the activation decision must remain `ros_soft_driver` or `ros_projection_only`; it must not claim board execution.
