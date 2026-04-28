from __future__ import annotations

"""Machine-readable command-to-runtime interface manifest.

The route registry proves which product commands exist. This manifest proves
what runtime interface each command handler must use and the validator scans the
handler implementation AST to make drift observable: required node attributes,
message/request/goal fields, runtime interface names, and terminal ACK status
must be present in the code path declared for the command.
"""

from dataclasses import dataclass, field
from pathlib import Path
import ast
from typing import Any, Iterable, Mapping

from robot_contracts.command_route_registry import command_route_entry


@dataclass(frozen=True, slots=True)
class CommandInterfaceSpec:
    """Semantic runtime interface contract for one operator command.

    Args:
        command_type: Product command identifier.
        handler_name: Expected bridge handler method.
        ros_kind: Runtime binding family: topic, service, action, coordinator,
            or an explicit composite such as ``action_with_service_fallback``.
        ros_name: Runtime ROS topic/service/action name or composite route.
        ros_type: ROS interface type in ``package/kind/Name`` form. Composite
            routes may use ``+`` to list branch interfaces.
        node_attributes: Attributes that must exist on ``RobotWebBridgeNode``
            and be referenced by the declared implementation methods.
        required_fields: Stable operator-facing field summary retained for
            generated governance artifacts.
        terminal_ack: Highest lifecycle status the handler can prove.
        implementation_methods: Handler/helper methods that together implement
            the command. The validator scans each method body.
        interface_fields: Concrete ROS message/request/goal fields that must be
            assigned by the scanned implementation methods.
        payload_fields: Payload keys that must be read or validated by the
            scanned implementation methods.
        required_ack_statuses: Lifecycle ACK statuses that must be emitted by
            the scanned implementation methods or their declared callbacks.
        runtime_names: ROS topic/service/action strings that must appear in the
            scanned implementation methods.
        forbidden_symbols: Symbols that must not appear in scanned methods.
        notes: Operator/auditor notes for boundary semantics.

    Returns:
        Immutable interface manifest entry.

    Raises:
        None.

    Boundary behavior:
        Topic commands are allowed to prove only queue/publication acceptance
        unless a downstream completion event is explicitly declared elsewhere.
    """

    command_type: str
    handler_name: str
    ros_kind: str
    ros_name: str
    ros_type: str
    node_attributes: tuple[str, ...]
    required_fields: tuple[str, ...]
    terminal_ack: str
    implementation_methods: tuple[str, ...] = ()
    interface_fields: tuple[str, ...] = ()
    payload_fields: tuple[str, ...] = ()
    required_ack_statuses: tuple[str, ...] = ()
    runtime_names: tuple[str, ...] = ()
    method_interface_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    forbidden_symbols: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def methods_to_scan(self) -> tuple[str, ...]:
        methods = (self.handler_name, *self.implementation_methods)
        seen: set[str] = set()
        ordered: list[str] = []
        for method in methods:
            value = str(method or '').strip()
            if value and value not in seen:
                seen.add(value)
                ordered.append(value)
        return tuple(ordered)

    def to_dict(self) -> dict[str, Any]:
        return {
            'commandType': self.command_type,
            'handlerName': self.handler_name,
            'rosKind': self.ros_kind,
            'rosName': self.ros_name,
            'rosType': self.ros_type,
            'nodeAttributes': list(self.node_attributes),
            'requiredFields': list(self.required_fields),
            'terminalAck': self.terminal_ack,
            'implementationMethods': list(self.methods_to_scan()),
            'interfaceFields': list(self.interface_fields),
            'payloadFields': list(self.payload_fields),
            'requiredAckStatuses': list(self.required_ack_statuses),
            'runtimeNames': list(self.runtime_names),
            'methodInterfaceFields': {key: list(value) for key, value in self.method_interface_fields.items()},
            'forbiddenSymbols': list(self.forbidden_symbols),
            'notes': list(self.notes),
        }


COMMAND_INTERFACE_MANIFEST: dict[str, CommandInterfaceSpec] = {
    'set_mode': CommandInterfaceSpec(
        command_type='set_mode',
        handler_name='handle_set_mode',
        ros_kind='service',
        ros_name='/robot/set_mode',
        ros_type='robot_msgs/srv/SetMode',
        node_attributes=('mode_client',),
        required_fields=('requested_by', 'reason', 'mode'),
        terminal_ack='completed',
        implementation_methods=('_queue_set_mode', 'on_set_mode_done', '_mode_command_outcome'),
        interface_fields=('requested_by', 'reason', 'mode'),
        payload_fields=('mode',),
        required_ack_statuses=('completed',),
        runtime_names=('/robot/set_mode',),
    ),
    'teleop_cmd': CommandInterfaceSpec(
        command_type='teleop_cmd',
        handler_name='handle_teleop',
        ros_kind='topic',
        ros_name='/robot/manual/cmd_vel',
        ros_type='geometry_msgs/msg/Twist',
        node_attributes=('manual_pub',),
        required_fields=('linear.x', 'angular.z'),
        terminal_ack='applied',
        interface_fields=('linear.x', 'angular.z'),
        payload_fields=('linear', 'vx', 'angular', 'wz'),
        required_ack_statuses=('applied',),
        runtime_names=('/robot/manual/cmd_vel',),
        notes=('latest-only fire-and-forget command; downstream controller owns final actuation.',),
    ),
    'stop_now': CommandInterfaceSpec(
        command_type='stop_now',
        handler_name='handle_stop_now',
        ros_kind='topic',
        ros_name='/robot/manual/cmd_vel',
        ros_type='geometry_msgs/msg/Twist',
        node_attributes=('manual_pub',),
        required_fields=('linear.x', 'angular.z'),
        terminal_ack='applied',
        interface_fields=('linear.x', 'angular.z'),
        required_ack_statuses=('applied',),
        runtime_names=('/robot/manual/cmd_vel',),
    ),
    'start_patrol': CommandInterfaceSpec(
        command_type='start_patrol',
        handler_name='handle_start_patrol',
        ros_kind='action',
        ros_name='/robot/actions/start_patrol',
        ros_type='robot_msgs/action/StartPatrol',
        node_attributes=('command_surface',),
        required_fields=('requested_by', 'reason', 'trace_id'),
        terminal_ack='completed',
        implementation_methods=('_dispatch_patrol_action', 'on_patrol_goal_response', 'on_patrol_result'),
        interface_fields=('requested_by', 'reason', 'trace_id'),
        required_ack_statuses=('accepted', 'completed'),
        runtime_names=('/robot/actions/start_patrol',),
    ),
    'pause_patrol': CommandInterfaceSpec(
        command_type='pause_patrol',
        handler_name='handle_pause_patrol',
        ros_kind='action+service',
        ros_name='/robot/actions/start_patrol cancel + /robot/set_mode',
        ros_type='robot_msgs/action/StartPatrol + robot_msgs/srv/SetMode',
        node_attributes=('mode_client',),
        required_fields=('requested_by', 'reason', 'mode'),
        terminal_ack='completed',
        implementation_methods=('_queue_set_mode', '_request_cancel', 'on_set_mode_done', '_mode_command_outcome'),
        interface_fields=('requested_by', 'reason', 'mode'),
        required_ack_statuses=('accepted', 'completed'),
        runtime_names=('/robot/set_mode',),
    ),
    'stop_patrol': CommandInterfaceSpec(
        command_type='stop_patrol',
        handler_name='handle_stop_patrol',
        ros_kind='action+service',
        ros_name='/robot/actions/start_patrol cancel + /robot/set_mode',
        ros_type='robot_msgs/action/StartPatrol + robot_msgs/srv/SetMode',
        node_attributes=('mode_client',),
        required_fields=('requested_by', 'reason', 'mode'),
        terminal_ack='completed',
        implementation_methods=('_queue_set_mode', '_request_cancel', 'on_set_mode_done', '_mode_command_outcome'),
        interface_fields=('requested_by', 'reason', 'mode'),
        required_ack_statuses=('accepted', 'completed'),
        runtime_names=('/robot/set_mode',),
    ),
    'resume_from_safe_stop': CommandInterfaceSpec(
        command_type='resume_from_safe_stop',
        handler_name='handle_resume_from_safe_stop',
        ros_kind='service',
        ros_name='/robot/set_mode',
        ros_type='robot_msgs/srv/SetMode',
        node_attributes=('mode_client',),
        required_fields=('requested_by', 'reason', 'mode'),
        terminal_ack='completed',
        implementation_methods=('_queue_set_mode', 'on_set_mode_done', '_mode_command_outcome'),
        interface_fields=('requested_by', 'reason', 'mode'),
        required_ack_statuses=('completed',),
        runtime_names=('/robot/set_mode',),
    ),
    'estop': CommandInterfaceSpec(
        command_type='estop',
        handler_name='handle_estop',
        ros_kind='service',
        ros_name='/robot/set_mode',
        ros_type='robot_msgs/srv/SetMode',
        node_attributes=('mode_client',),
        required_fields=('requested_by', 'reason', 'mode'),
        terminal_ack='completed',
        implementation_methods=('_queue_set_mode', 'on_set_mode_done', '_mode_command_outcome'),
        interface_fields=('requested_by', 'reason', 'mode'),
        required_ack_statuses=('completed',),
        runtime_names=('/robot/set_mode',),
    ),
    'apply_param_draft': CommandInterfaceSpec(
        command_type='apply_param_draft',
        handler_name='handle_apply_param_draft',
        ros_kind='coordinator',
        ros_name='/robot/runtime_params/apply_result',
        ros_type='std_msgs/msg/String',
        node_attributes=('runtime_param_coordinator', 'runtime_param_pub'),
        required_fields=('transaction_id', 'params'),
        terminal_ack='completed',
        payload_fields=('params',),
        required_ack_statuses=('completed',),
    ),
    'apply_param_profile': CommandInterfaceSpec(
        command_type='apply_param_profile',
        handler_name='handle_apply_param_profile',
        ros_kind='coordinator',
        ros_name='/robot/runtime_params/apply_result',
        ros_type='std_msgs/msg/String',
        node_attributes=('runtime_param_coordinator', 'runtime_param_pub'),
        required_fields=('profileName',),
        terminal_ack='completed',
        payload_fields=('profileName',),
        required_ack_statuses=('completed',),
    ),
    'speak_fixed_text': CommandInterfaceSpec(
        command_type='speak_fixed_text',
        handler_name='handle_speak_fixed_text',
        ros_kind='topic',
        ros_name='/robot/speak_req',
        ros_type='robot_msgs/msg/SpeakRequest',
        node_attributes=('speak_pub',),
        required_fields=('text_id', 'priority', 'requested_by', 'trace_id'),
        terminal_ack='applied',
        interface_fields=('text_id', 'priority', 'requested_by', 'trace_id'),
        payload_fields=('text', 'text_id', 'textId', 'priority'),
        required_ack_statuses=('applied',),
        runtime_names=('/robot/speak_req',),
        forbidden_symbols=('speak_client', '/robot/voice/speak', 'TriggerSpeak'),
        notes=('Topic ACK means queued into robot_voice; board/audio completion is target-environment evidence.',),
    ),
    'reset_fault': CommandInterfaceSpec(
        command_type='reset_fault',
        handler_name='handle_reset_fault',
        ros_kind='service',
        ros_name='/robot/reset_fault',
        ros_type='robot_msgs/srv/ResetFault',
        node_attributes=('reset_client',),
        required_fields=('requested_by', 'reason', 'trace_id'),
        terminal_ack='completed',
        implementation_methods=('on_reset_done',),
        interface_fields=('requested_by', 'reason', 'trace_id'),
        required_ack_statuses=('completed',),
        runtime_names=('/robot/reset_fault',),
    ),
    'save_snapshot': CommandInterfaceSpec(
        command_type='save_snapshot',
        handler_name='handle_save_snapshot',
        ros_kind='action_with_service_fallback',
        ros_name='/robot/actions/save_snapshot -> /robot/save_snapshot',
        ros_type='robot_msgs/action/SaveSnapshotTask + robot_msgs/srv/SaveSnapshot',
        node_attributes=('snapshot_client',),
        required_fields=('reason', 'trace_id'),
        terminal_ack='completed',
        implementation_methods=('_dispatch_snapshot_action', 'on_snapshot_done', 'on_snapshot_action_result'),
        interface_fields=('reason', 'trace_id'),
        payload_fields=('reason',),
        required_ack_statuses=('completed',),
        runtime_names=('/robot/actions/save_snapshot', '/robot/save_snapshot'),
        method_interface_fields={'handle_save_snapshot': ('reason', 'trace_id'), '_dispatch_snapshot_action': ('requested_by', 'reason', 'trace_id')},
        forbidden_symbols=('filename',),
        notes=('Action route is preferred; service fallback must use SaveSnapshot.srv request fields only.',),
    ),
}


class _MethodFacts(ast.NodeVisitor):
    """Extract semantic facts from command implementation method bodies."""

    def __init__(self) -> None:
        self.assigned_fields: set[str] = set()
        self.attr_chains: set[str] = set()
        self.node_attributes: set[str] = set()
        self.payload_fields: set[str] = set()
        self.string_literals: set[str] = set()
        self.ack_statuses: set[str] = set()
        self.call_names: set[str] = set()

    def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802
        if isinstance(node.value, str):
            self.string_literals.add(node.value)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:  # noqa: N802
        chain = _attribute_chain(node)
        if chain:
            self.attr_chains.add(chain)
            if '.node.' in chain:
                parts = chain.split('.node.', 1)[1].split('.')
                if parts and parts[0]:
                    self.node_attributes.add(parts[0])
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802
        for target in node.targets:
            self._record_assignment_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:  # noqa: N802
        self._record_assignment_target(node.target)
        self.generic_visit(node)

    def _record_assignment_target(self, target: ast.AST) -> None:
        if isinstance(target, ast.Attribute):
            chain = _attribute_chain(target)
            if chain:
                self.assigned_fields.add(_strip_local_root(chain))

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
        call_name = _call_name(node.func)
        if call_name:
            self.call_names.add(call_name)
        if isinstance(node.func, ast.Attribute):
            owner = _attribute_chain(node.func.value)
            if owner and '.node.' in owner:
                parts = owner.split('.node.', 1)[1].split('.')
                if parts and parts[0]:
                    self.node_attributes.add(parts[0])
        self._record_payload_get(node)
        self._record_ack_call(node, call_name)
        self.generic_visit(node)

    def _record_payload_get(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute):
            return
        if node.func.attr != 'get':
            return
        owner = _attribute_chain(node.func.value)
        if owner != 'payload':
            return
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            self.payload_fields.add(node.args[0].value)

    def _record_ack_call(self, node: ast.Call, call_name: str) -> None:
        if call_name.endswith('._send_ack') and len(node.args) >= 3:
            status = _literal_str(node.args[2])
            if status:
                self.ack_statuses.add(status)
        if call_name.endswith('._finalize_action'):
            status = _keyword_literal(node, 'lifecycle_status')
            if status:
                self.ack_statuses.add(status)
        if call_name.endswith('._record_phase') and len(node.args) >= 4:
            status = _literal_str(node.args[3])
            if status:
                self.ack_statuses.add(status)
        if call_name.endswith('._reject'):
            self.ack_statuses.add('rejected')
        if call_name.endswith('._deny'):
            self.ack_statuses.add('denied')


def command_interface_manifest_payload() -> dict[str, dict[str, Any]]:
    """Serialize the command interface manifest for generated governance artifacts."""
    return {name: spec.to_dict() for name, spec in sorted(COMMAND_INTERFACE_MANIFEST.items())}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _parse_ros_fields(path: Path) -> set[str]:
    fields: set[str] = set()
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line == '---':
            break
        if '=' in line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            fields.add(parts[1].strip())
    return fields


def _interface_files_for_ros_type(ros_type: str, *, repo_root: Path | None = None) -> list[Path]:
    files: list[Path] = []
    base = repo_root or _repo_root()
    for part in str(ros_type or '').split('+'):
        item = part.strip()
        if not item.startswith('robot_msgs/'):
            continue
        pieces = item.split('/', 2)
        if len(pieces) != 3:
            continue
        _, kind, name = pieces
        suffix = {'msg': 'msg', 'srv': 'srv', 'action': 'action'}.get(kind)
        if suffix is None:
            continue
        files.append(base / 'ros2_ws' / 'src' / 'robot_msgs' / suffix / f'{name}.{suffix}')
    return files


def _load_method_facts(paths: Iterable[Path]) -> tuple[dict[str, ast.FunctionDef], dict[str, _MethodFacts], list[str]]:
    methods: dict[str, ast.FunctionDef] = {}
    facts: dict[str, _MethodFacts] = {}
    errors: list[str] = []
    for path in paths:
        if not path.is_file():
            errors.append(f'missing_scan_file:{path}')
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:
            errors.append(f'syntax_error:{path}:{exc}')
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                methods[node.name] = node
                visitor = _MethodFacts()
                visitor.visit(node)
                facts[node.name] = visitor
    return methods, facts, errors


def _attribute_chain(node: ast.AST) -> str:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return '.'.join(reversed(parts))
    if isinstance(current, ast.Call):
        call = _call_name(current.func)
        if call:
            parts.append(call)
            return '.'.join(reversed(parts))
    return '.'.join(reversed(parts))


def _strip_local_root(chain: str) -> str:
    parts = chain.split('.')
    if len(parts) > 1 and parts[0] in {'req', 'goal', 'twist', 'msg'}:
        return '.'.join(parts[1:])
    return chain


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        owner = _attribute_chain(func.value)
        return f'{owner}.{func.attr}' if owner else func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ''


def _literal_str(node: ast.AST) -> str:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ''


def _keyword_literal(node: ast.Call, name: str) -> str:
    for keyword in node.keywords:
        if keyword.arg == name:
            return _literal_str(keyword.value)
    return ''


def _merge_facts(names: Iterable[str], method_facts: Mapping[str, _MethodFacts]) -> _MethodFacts:
    merged = _MethodFacts()
    for name in names:
        facts = method_facts.get(name)
        if facts is None:
            continue
        merged.assigned_fields.update(facts.assigned_fields)
        merged.attr_chains.update(facts.attr_chains)
        merged.node_attributes.update(facts.node_attributes)
        merged.payload_fields.update(facts.payload_fields)
        merged.string_literals.update(facts.string_literals)
        merged.ack_statuses.update(facts.ack_statuses)
        merged.call_names.update(facts.call_names)
    return merged


def _field_present(required: str, assigned_fields: set[str]) -> bool:
    if required in assigned_fields:
        return True
    # A dotted field such as linear.x is satisfied only by the dotted assignment.
    if '.' in required:
        return required in assigned_fields
    return required in {field.split('.', 1)[0] for field in assigned_fields}


def validate_command_interface_manifest(*, repo_root: Path | None = None) -> list[str]:
    """Validate route, handler, AST implementation, and ROS field alignment.

    Args:
        repo_root: Repository root override used by tests and scripts.

    Returns:
        Validation error strings. Empty means the semantic manifest is aligned.

    Raises:
        None. Missing files are reported as stable validation errors.
    """
    base = repo_root or _repo_root()
    errors: list[str] = []
    component_dir = base / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'components'
    node_file = base / 'ros2_ws' / 'src' / 'robot_web_bridge' / 'robot_web_bridge' / 'web_bridge_node.py'
    scan_files = (
        component_dir / 'command_handlers.py',
        component_dir / 'command_execution_service.py',
        component_dir / 'runtime_param_command_service.py',
    )
    method_nodes, method_facts, scan_errors = _load_method_facts(scan_files)
    errors.extend(scan_errors)
    if not node_file.is_file():
        errors.append(f'missing_node_file:{node_file}')
        return errors
    node_source = node_file.read_text(encoding='utf-8')

    for command, spec in sorted(COMMAND_INTERFACE_MANIFEST.items()):
        route = command_route_entry(command)
        if route is None:
            errors.append(f'{command}:missing_command_route')
            continue
        if route.bridge_handler != spec.handler_name:
            errors.append(f'{command}:handler_mismatch:route={route.bridge_handler}:manifest={spec.handler_name}')
        for method_name in spec.methods_to_scan():
            if method_name not in method_nodes:
                errors.append(f'{command}:implementation_method_not_found:{method_name}')
        facts = _merge_facts(spec.methods_to_scan(), method_facts)
        for attr in spec.node_attributes:
            if f'self.{attr}' not in node_source and f'.{attr}' not in node_source:
                errors.append(f'{command}:missing_node_attribute:{attr}')
            if attr not in facts.node_attributes and spec.ros_kind not in {'action', 'coordinator'}:
                errors.append(f'{command}:node_attribute_not_used_by_implementation:{attr}')
        interfaces = _interface_files_for_ros_type(spec.ros_type, repo_root=base)
        if interfaces:
            field_sets: dict[str, set[str]] = {}
            for iface in interfaces:
                try:
                    field_sets[iface.name] = _parse_ros_fields(iface)
                except OSError:
                    errors.append(f'{command}:missing_interface_file:{iface}')
            if field_sets:
                union_fields = set().union(*field_sets.values())
                interface_names = '+'.join(field_sets)
                for field in spec.interface_fields:
                    top = field.split('.', 1)[0]
                    if top and top not in union_fields:
                        errors.append(f'{command}:missing_interface_field:{interface_names}:{field}')
        for method_name, method_fields in spec.method_interface_fields.items():
            method_fact = method_facts.get(method_name)
            if method_fact is None:
                errors.append(f'{command}:method_interface_fields_method_not_found:{method_name}')
                continue
            for field in method_fields:
                if not _field_present(field, method_fact.assigned_fields):
                    errors.append(f'{command}:method_interface_field_not_assigned:{method_name}:{field}')
        for field in spec.interface_fields:
            if not _field_present(field, facts.assigned_fields):
                errors.append(f'{command}:interface_field_not_assigned:{field}')
        for field in spec.payload_fields:
            if field not in facts.payload_fields and field not in facts.string_literals:
                errors.append(f'{command}:payload_field_not_read:{field}')
        for status in spec.required_ack_statuses:
            if status not in facts.ack_statuses and status not in facts.string_literals:
                errors.append(f'{command}:required_ack_status_not_emitted:{status}')
        if spec.terminal_ack not in facts.ack_statuses and spec.terminal_ack not in facts.string_literals and spec.required_ack_statuses:
            errors.append(f'{command}:terminal_ack_not_emitted:{spec.terminal_ack}')
        for runtime_name in spec.runtime_names:
            if runtime_name not in facts.string_literals and runtime_name not in node_source:
                errors.append(f'{command}:runtime_name_not_referenced:{runtime_name}')
        combined_literals_and_attrs = set(facts.string_literals) | set(facts.attr_chains) | set(facts.call_names)
        for forbidden in spec.forbidden_symbols:
            if any(forbidden in item for item in combined_literals_and_attrs):
                errors.append(f'{command}:forbidden_symbol_in_implementation:{forbidden}')
    return errors
