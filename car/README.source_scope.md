This repository is delivered as a canonical-only source release.

Canonical editable Ubuntu-side source root:
- repository root `./`

There is no generated compatibility shell inside this package.

The source tree contains:
- `robot_frontend/`
- `ros2_ws/`
- `scripts/`
- `tools/`
- `docs/`
- startup scripts at the repository root
- embedded source trees under `esp32s3_code/` and `stm32_code/`

Review and code changes must target the repository root directly.
The split-snapshot maintenance scripts remain available for compatibility with
upstream repositories, but they are no-op checks in this canonical-only package.
