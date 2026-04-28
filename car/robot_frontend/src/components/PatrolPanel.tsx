import { useEffect, useMemo, useState } from 'react';

import { robotBridge } from '@/bridge/client';
import { commandButtonState } from '@/bridge/commandPolicy';
import { fetchRuntimeMissionCatalog } from '@/bridge/runtimeMissionCatalog';
import { FeatureMaturityPills } from '@/components/FeatureMaturityPills';
import { SectionCard } from '@/components/SectionCard';
import { PRODUCT_MISSION_CATALOG, type GeneratedMissionCatalog, type GeneratedMissionCatalogEntry } from '@/generated/missionCatalog';
import { useRobotStore } from '@/store/useRobotStore';

export function PatrolPanel() {
  const task = useRobotStore((state) => state.task);
  const runtime = useRobotStore((state) => state.runtime);
  const ui = useRobotStore((state) => state.ui);
  const [missionCatalog, setMissionCatalog] = useState<GeneratedMissionCatalog>(PRODUCT_MISSION_CATALOG);
  const [catalogSource, setCatalogSource] = useState<'bootstrap' | 'runtime'>('bootstrap');
  const [catalogError, setCatalogError] = useState<string>('');
  const missionEntries = useMemo<GeneratedMissionCatalogEntry[]>(() => Object.values(missionCatalog.missions), [missionCatalog]);
  const [selectedMissionId, setSelectedMissionId] = useState<string>(PRODUCT_MISSION_CATALOG.defaultMissionId);

  useEffect(() => {
    const controller = new AbortController();
    void fetchRuntimeMissionCatalog(controller.signal)
      .then((catalog) => {
        setMissionCatalog(catalog);
        setCatalogSource('runtime');
        setCatalogError('');
        setSelectedMissionId((current) => (Object.prototype.hasOwnProperty.call(catalog.missions, current) ? current : catalog.defaultMissionId));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : 'failed to load runtime mission catalog';
        setCatalogError(message);
        useRobotStore.getState().pushLog({
          level: 'WARN',
          domain: 'SYSTEM',
          message: '运行时 mission catalog 加载失败，当前页面回退到构建时合同快照。',
          details: message,
        });
      });
    return () => controller.abort();
  }, []);

  const selectedMission = useMemo(
    () => missionEntries.find((item) => item.missionId === selectedMissionId) ?? missionEntries[0],
    [missionEntries, selectedMissionId],
  );
  const startPayload = useMemo(() => ({
    source: 'frontend' as const,
    missionId: selectedMission?.missionId,
    routeName: selectedMission?.routeName,
    taskProfile: selectedMission?.taskProfile,
  }), [selectedMission]);
  const startPatrol = commandButtonState('start_patrol', startPayload);
  const pausePatrol = commandButtonState('pause_patrol', { source: 'frontend' });
  const stopPatrol = commandButtonState('stop_patrol', { source: 'frontend' });

  return (
    <SectionCard title="巡检任务" right={<FeatureMaturityPills featureIds={['operator.patrol_execution']} />}>
      <div className="patrol-summary">
        <div>
          <span>任务状态</span>
          <strong>{task.patrolStatus}</strong>
        </div>
        <div>
          <span>运行相位</span>
          <strong>{runtime.taskPhase}</strong>
        </div>
        <div>
          <span>当前点位</span>
          <strong>{task.currentWaypoint ?? '--'}</strong>
        </div>
        <div>
          <span>完成进度</span>
          <strong>{Math.round(task.progress * 100)}%</strong>
        </div>
        <div>
          <span>Action 相位</span>
          <strong>{task.actionPhase ?? '--'}</strong>
        </div>
        <div>
          <span>Action 消息</span>
          <strong>{task.actionMessage ?? '--'}</strong>
        </div>
      </div>
      <div className="patrol-summary">
        <label>
          <span>任务模板</span>
          <select value={selectedMission?.missionId ?? missionCatalog.defaultMissionId} onChange={(event) => setSelectedMissionId(event.target.value)}>
            {missionEntries.map((entry) => (
              <option key={entry.missionId} value={entry.missionId}>{entry.title}</option>
            ))}
          </select>
        </label>
        <div>
          <span>目录来源</span>
          <strong>{catalogSource === 'runtime' ? '9100 /api/v1/missions' : 'bootstrap contract'}</strong>
        </div>
        <div>
          <span>路径名称</span>
          <strong>{selectedMission?.routeName ?? '--'}</strong>
        </div>
        <div>
          <span>任务画像</span>
          <strong>{selectedMission?.taskProfile ?? '--'}</strong>
        </div>
        <div>
          <span>恢复策略</span>
          <strong>{selectedMission?.resumePolicy ?? '--'}</strong>
        </div>
      </div>
      {catalogError ? <p className="muted">运行时 mission catalog 加载失败：{catalogError}</p> : null}
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, task.progress * 100))}%` }} />
      </div>
      <div className="inline-actions">
        <button className="primary-btn" title={startPatrol.reason} disabled={ui.demoReadonly || startPatrol.disabled || !selectedMission} onClick={() => selectedMission && robotBridge.send('start_patrol', startPayload, `开始巡检任务：${selectedMission.title}`)}>开始巡检</button>
        <button className="ghost-btn" title={pausePatrol.reason} disabled={ui.demoReadonly || pausePatrol.disabled} onClick={() => robotBridge.send('pause_patrol', { source: 'frontend' }, '暂停巡检任务')}>暂停巡检</button>
        <button className="danger-btn" title={stopPatrol.reason} disabled={ui.demoReadonly || stopPatrol.disabled} onClick={() => robotBridge.send('stop_patrol', { source: 'frontend' }, '停止巡检任务')}>停止巡检</button>
      </div>
      <div className="waypoint-list">
        {(selectedMission?.stages ?? []).map((stage) => (
          <div key={stage.stageId} className="waypoint-item status-pending">
            <strong>{stage.title}</strong>
            <span>{stage.kind}</span>
            {stage.routeName ? <small className="muted">route={stage.routeName}</small> : null}
          </div>
        ))}
      </div>
      <div className="waypoint-list">
        {task.waypoints.map((point) => (
          <div key={point.id} className={`waypoint-item status-${point.status}`}>
            <strong>{point.label}</strong>
            <span>{point.status}</span>
            {point.note ? <small className="muted">{point.note}</small> : null}
          </div>
        ))}
      </div>
      <p className="muted">巡检页现在会先读取 9100 正式产品接口（/product-interface → /missions）；仅在 API 不可用时才回退到构建时合同快照。</p>
    </SectionCard>
  );
}
