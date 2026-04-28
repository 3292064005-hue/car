Audience: auditors / releasers
Scope: executed validation evidence for this delivery
Source of truth: command outputs captured during packaging and review
Status: evidence-artifact
- ArtifactId: inspection_robot_source:501f44c1e1d68489
- WorkspaceId: single_root_canonical:f374810d6041
- LayoutMode: single_root_canonical
- WorkspaceManifestSha256: f374810d6041c70a9fb42da59e7cc1955f6dcdf145b2db1f3e356860c522b688
- SourceTreeSha256: 501f44c1e1d684897ece21aac373303282674d2ed91b7cfbc4265d676a4aab36
- CanonicalRootToken: <canonical-root>
- EvidencePathPolicy: portable_placeholder_tokens_only

# Validation evidence

This file records focused validation commands rerun while producing this package.
It is intentionally narrower than a full release gate and is not proof of real target-environment execution.

## Commands rerun

### `python -S py_compile targeted hardware / contract / resolver files`
- Exit status: 0
- Captured output:

```text
PY_COMPILE_OK 13
```

### `python -S scripts/resolve_runtime_surface_config.py --profile hardware --surface backend --output <temp-root>/hw.json`
- Exit status: 0
- Captured output:

```text
compatibilitySurfaceRole=ros_soft_driver
effectiveCompatibilitySurfaceRole=ros_soft_driver
activationDecision=activate
validationStatus=accepted_soft_driver_no_board_claim
effectiveBoardExecutionConfirmed=False
effectiveClaimScope=ros_runtime_soft_driver_boundary_only
ROBOT_EFFECTIVE_HARDWARE_SURFACE_ROLE=ros_soft_driver
ROBOT_EFFECTIVE_BOARD_EXECUTION_CONFIRMED=false
```

### `python -S scripts/resolve_runtime_surface_config.py --profile mock --surface frontend --output <temp-root>/mock.json`
- Exit status: 0
- Captured output:

```text
compatibilitySurfaceRole=ros_soft_driver
effectiveCompatibilitySurfaceRole=ros_projection_only
activationDecision=activate
validationStatus=downgraded_to_projection
effectiveBoardExecutionConfirmed=False
effectiveClaimScope=ros_projection_observability_only
```

### `manual hardware activation policy assertions`
- Exit status: 0
- Captured output:

```text
MANUAL_HARDWARE_ROLE_TESTS_OK
```

### `python -S scripts/check_capability_registry_consistency.py`
- Exit status: 0
- Captured output:

```json
{
  "status": "ok",
  "capabilityCount": 17,
  "validationErrors": []
}
```

### `python -S scripts/check_feature_admission.py`
- Exit status: 0
- Captured output:

```text
STATUS:0
```

## Validation boundaries

- No target-environment acceptance was rerun in this sandbox.
- The prior HIL artifact was not promoted as current board-execution proof after code/config changes.
- Default hardware activation is intentionally limited to `ros_soft_driver` with no board-execution claim.
