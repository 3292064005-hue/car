import { useEffect, useMemo, useRef, useState } from 'react';
import { robotBridge } from '@/bridge/client';
import { SectionCard } from '@/components/SectionCard';
import { clamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

type TeleopIntent = { forward: boolean; backward: boolean; left: boolean; right: boolean };

const emptyIntent: TeleopIntent = { forward: false, backward: false, left: false, right: false };

export function TeleopPanel() {
  const motion = useRobotStore((state) => state.motion);
  const params = useRobotStore((state) => state.profiles.applied);
  const connection = useRobotStore((state) => state.connection);
  const ui = useRobotStore((state) => state.ui);
  const [intent, setIntent] = useState<TeleopIntent>(emptyIntent);
  const [armed, setArmed] = useState(false);
  const pressedRef = useRef<Set<string>>(new Set());

  const disabled = ui.demoReadonly;

  const velocity = useMemo(() => {
    const linear = intent.forward === intent.backward ? 0 : intent.forward ? params.maxLinearSpeed : -params.maxLinearSpeed;
    const angular = intent.left === intent.right ? 0 : intent.left ? params.maxAngularSpeed : -params.maxAngularSpeed;
    return {
      linear: clamp(linear, -params.maxLinearSpeed, params.maxLinearSpeed),
      angular: clamp(angular, -params.maxAngularSpeed, params.maxAngularSpeed)
    };
  }, [intent, params.maxAngularSpeed, params.maxLinearSpeed]);

  useEffect(() => {
    const stopAll = () => {
      setIntent(emptyIntent);
      setArmed(false);
      robotBridge.send('stop_now', { source: 'frontend' }, '窗口失焦或释放控制时停车');
    };

    const onDown = (event: KeyboardEvent) => {
      if (pressedRef.current.has(event.code)) return;
      pressedRef.current.add(event.code);
      if (event.code === 'ShiftLeft' || event.code === 'ShiftRight') setArmed(true);
      if (event.code === 'KeyW') setIntent((prev) => ({ ...prev, forward: true }));
      if (event.code === 'KeyS') setIntent((prev) => ({ ...prev, backward: true }));
      if (event.code === 'KeyA') setIntent((prev) => ({ ...prev, left: true }));
      if (event.code === 'KeyD') setIntent((prev) => ({ ...prev, right: true }));
      if (event.code === 'Space') stopAll();
    };

    const onUp = (event: KeyboardEvent) => {
      pressedRef.current.delete(event.code);
      if (event.code === 'ShiftLeft' || event.code === 'ShiftRight') setArmed(false);
      if (event.code === 'KeyW') setIntent((prev) => ({ ...prev, forward: false }));
      if (event.code === 'KeyS') setIntent((prev) => ({ ...prev, backward: false }));
      if (event.code === 'KeyA') setIntent((prev) => ({ ...prev, left: false }));
      if (event.code === 'KeyD') setIntent((prev) => ({ ...prev, right: false }));
    };

    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    window.addEventListener('blur', stopAll);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
      window.removeEventListener('blur', stopAll);
    };
  }, [motion.mode]);

  useEffect(() => {
    if (!armed || ui.demoReadonly) return;
    const timer = window.setInterval(() => {
      robotBridge.send('teleop_cmd', { linear: velocity.linear, angular: velocity.angular, source: 'frontend' }, '持续手动控制');
    }, 120);
    return () => window.clearInterval(timer);
  }, [armed, ui.demoReadonly, velocity.angular, velocity.linear]);

  const holdIntent = (patch: Partial<TeleopIntent>) => {
    setArmed(true);
    setIntent({ ...emptyIntent, ...patch });
  };

  const releaseIntent = () => {
    setArmed(false);
    setIntent(emptyIntent);
    robotBridge.send('stop_now', { source: 'frontend' }, '释放 deadman 停车');
  };

  return (
    <SectionCard title="手动控制">
      <div className="teleop-grid">
        <div className="teleop-readout">
          <p><strong>当前模式：</strong>{motion.mode}</p>
          <p><strong>deadman：</strong>{armed ? '已压住' : '未压住'}</p>
          <p><strong>目标线速度：</strong>{velocity.linear.toFixed(2)} m/s</p>
          <p><strong>目标角速度：</strong>{velocity.angular.toFixed(2)} rad/s</p>
          <p><strong>风险提示：</strong>{motion.mode !== 'MANUAL' || connection.reconnecting ? '当前不满足推荐 teleop 条件，命令仍会发送，最终以后端 ACK 为准。' : '当前满足推荐 teleop 条件。'}</p>
        </div>
        <div className="teleop-actions">
          <button className="primary-btn" disabled={ui.demoReadonly} onClick={() => robotBridge.send('set_mode', { mode: 'MANUAL', source: 'frontend' }, '进入 MANUAL')}>
            进入 MANUAL
          </button>
          <button className="ghost-btn" disabled={ui.demoReadonly} onClick={() => robotBridge.send('set_mode', { mode: 'IDLE', source: 'frontend' }, '回到 IDLE')}>
            回到 IDLE
          </button>
          <button className="danger-btn" disabled={ui.demoReadonly} onClick={() => robotBridge.send('stop_now', { source: 'frontend' }, '立即停车')}>
            立即停车
          </button>
        </div>
      </div>
      <div className="teleop-buttons teleop-button-grid">
        <button className="ghost-btn" disabled={disabled} onMouseDown={() => holdIntent({ forward: true })} onMouseUp={releaseIntent} onMouseLeave={releaseIntent}>按住前进</button>
        <button className="ghost-btn" disabled={disabled} onMouseDown={() => holdIntent({ backward: true })} onMouseUp={releaseIntent} onMouseLeave={releaseIntent}>按住后退</button>
        <button className="ghost-btn" disabled={disabled} onMouseDown={() => holdIntent({ left: true })} onMouseUp={releaseIntent} onMouseLeave={releaseIntent}>按住左转</button>
        <button className="ghost-btn" disabled={disabled} onMouseDown={() => holdIntent({ right: true })} onMouseUp={releaseIntent} onMouseLeave={releaseIntent}>按住右转</button>
      </div>
      <p className="muted">键盘持续控制：先进入 MANUAL，再按住 Shift 作为 deadman，同时用 W/A/S/D 控制方向；空格立即停车。</p>
    </SectionCard>
  );
}
