import { Link, Outlet, useLocation } from 'react-router-dom';
import { AlertTriangle, Shield, ToggleLeft, ToggleRight } from 'lucide-react';
import { NAV_ITEMS } from '@/shared/constants';
import { cn, formatRelativeAge } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';
import { StatusPill } from '@/components/StatusPill';

export function MainLayout() {
  const location = useLocation();
  const motion = useRobotStore((state) => state.motion);
  const fault = useRobotStore((state) => state.fault);
  const connection = useRobotStore((state) => state.connection);
  const ui = useRobotStore((state) => state.ui);
  const runtime = useRobotStore((state) => state.runtime);
  const setUiFilter = useRobotStore((state) => state.setUiFilter);

  return (
    <div className={cn('app-shell', fault.safeStopActive || fault.estopActive ? 'alarm-shell' : '')}>
      <aside className="sidebar">
        <div className="brand-block">
          <h1>巡检机器人控制台</h1>
          <p>本地上位机 / ROS2 Web Frontend / V4</p>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <Link key={item.path} to={item.path} className={cn('nav-link', location.pathname === item.path ? 'active' : '')}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <StatusPill label={ui.demoReadonly ? '只读演示模式' : '可写控制模式'} tone={ui.demoReadonly ? 'warning' : 'success'} />
          <button className="ghost-btn full-width" onClick={() => setUiFilter({ demoReadonly: !ui.demoReadonly })}>
            {ui.demoReadonly ? <ToggleLeft size={16} /> : <ToggleRight size={16} />}切换演示模式
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar enhanced-topbar">
          <div className="topbar-chip">
            <strong>当前模式</strong>
            <span>{motion.mode}</span>
          </div>
          <div className="topbar-chip">
            <strong>bridge</strong>
            <span>{connection.bridgeConnected ? '在线' : '离线'}</span>
          </div>
          <div className="topbar-chip">
            <strong>心跳</strong>
            <span>{formatRelativeAge(connection.lastHeartbeatAt)}</span>
          </div>
          <div className="topbar-chip">
            <strong>安全相位</strong>
            <span>{runtime.safetyPhase}</span>
          </div>
          <div className="topbar-chip">
            <strong>传输</strong>
            <span>{connection.transportType}</span>
          </div>
          <div className="topbar-chip">
            <strong>协议</strong>
            <span>{connection.protocolVersion}</span>
          </div>
          <div className="topbar-alerts">
            {fault.safeStopActive ? <StatusPill label="SAFE_STOP" tone="danger" /> : null}
            {fault.estopActive ? <StatusPill label="急停激活" tone="danger" /> : null}
            {runtime.lastRejectedReason ? <StatusPill label="已拦截危险操作" tone="warning" /> : null}
            {!fault.estopActive && fault.safeStopActive ? <Shield size={18} /> : null}
            {fault.estopActive ? <AlertTriangle size={18} /> : null}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
