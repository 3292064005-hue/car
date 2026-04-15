import { MODE_ORDER } from '@/shared/constants';
import { canTransitionMode } from '@/machines/modeRules';
import { robotBridge } from '@/bridge/client';
import { commandButtonState } from '@/bridge/commandPolicy';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { useRobotStore } from '@/store/useRobotStore';
import type { RobotMode } from '@/types/robot';

const riskyModes: RobotMode[] = ['SAFE_STOP', 'FAULT'];

export function ModePanel() {
  const motion = useRobotStore((state) => state.motion);
  const fault = useRobotStore((state) => state.fault);
  const power = useRobotStore((state) => state.power);
  const connection = useRobotStore((state) => state.connection);
  const ui = useRobotStore((state) => state.ui);

  return (
    <SectionCard
      title="模式状态"
      right={<StatusPill label={motion.mode} tone={riskyModes.includes(motion.mode) ? 'danger' : motion.mode === 'IDLE' ? 'neutral' : 'success'} />}
    >
      <div className="mode-grid">
        {MODE_ORDER.map((mode) => {
          const active = mode === motion.mode;
          const rule = canTransitionMode({ currentMode: motion.mode, targetMode: mode, fault, connection, power });
          const blockedByReadonly = ui.demoReadonly && !active;
          const commandState = commandButtonState('set_mode', { mode, source: 'frontend' });
          const disabled = active || blockedByReadonly || commandState.disabled || !rule.allowed;
          const title = blockedByReadonly
            ? '当前启用了本地演示锁，模式切换按钮已在浏览器侧禁用。'
            : (commandState.reason || rule.reason || '');
          return (
            <button
              key={mode}
              className={active ? 'mode-btn active' : 'mode-btn'}
              disabled={disabled}
              title={title}
              onClick={() => robotBridge.send('set_mode', { mode, source: 'frontend' }, `切换模式 -> ${mode}`)}
            >
              {mode}
            </button>
          );
        })}
      </div>
      <p className="muted">联机态模式裁决已以下位机/ROS2 权威快照为准；本地规则仅在离线或 Mock 传输时兜底。{connection.safeStopRequiresManualAck ? ' SAFE_STOP 当前仍需人工确认后恢复。' : ''}</p>
    </SectionCard>
  );
}
