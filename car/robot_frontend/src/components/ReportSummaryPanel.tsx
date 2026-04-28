import { Download } from 'lucide-react';
import { FeatureMaturityPills } from '@/components/FeatureMaturityPills';
import { SectionCard } from '@/components/SectionCard';
import { downloadText, exportCommandsAsCsv, exportLogsAsCsv, formatNumber, percentile, toJson, average } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';
import type { ReportSurfaceEntry } from '@/types/robot';

const REPORT_ORDER: Array<{ key: string; label: string }> = [
  { key: 'controlSummary', label: 'controlSummary' },
  { key: 'monitorSummary', label: 'monitorSummary' },
  { key: 'monitorDiagnostics', label: 'monitorDiagnostics' },
  { key: 'localizationSummary', label: 'localizationSummary' },
  { key: 'hardwareInterfaceSummary', label: 'hardwareInterfaceSummary' },
  { key: 'navigationStatus', label: 'navigationStatus' },
  { key: 'voiceIngressHealth', label: 'voiceIngressHealth' },
  { key: 'navigationPath', label: 'navigationPath' },
  { key: 'runtimeSupervision', label: 'runtimeSupervision' },
];

function severityLabel(entry?: ReportSurfaceEntry) {
  switch (entry?.severity) {
    case 'success':
      return '正常';
    case 'warn':
      return '退化';
    case 'error':
      return '异常';
    default:
      return '信息';
  }
}

function renderTypedDetails(entry?: ReportSurfaceEntry) {
  if (!entry) {
    return null;
  }
  const details = entry.details && typeof entry.details === 'object' ? entry.details as Record<string, unknown> : undefined;
  if (!details) {
    return entry.raw ? <pre className="code-block">{entry.raw}</pre> : null;
  }
  if (entry.kind === 'control_summary') {
    const arbitration = details.arbitration as Record<string, unknown> | undefined;
    const rejected = Array.isArray(details.rejectedCandidates) ? details.rejectedCandidates.length : 0;
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>winner</span><strong>{String(details.winner ?? '-')}</strong></div>
        <div className="kv-item"><span>safetyReason</span><strong>{String(details.safetyReason ?? '-')}</strong></div>
        <div className="kv-item"><span>powerReason</span><strong>{String(details.powerReason ?? '-')}</strong></div>
        <div className="kv-item"><span>selectedAgeSec</span><strong>{String(details.selectedAgeSec ?? '-')}</strong></div>
        <div className="kv-item"><span>selectedCommand</span><strong>{String(details.selectedCommand ?? '-')}</strong></div>
        <div className="kv-item"><span>arbitration</span><strong>{JSON.stringify(arbitration ?? {})}</strong></div>
        <div className="kv-item"><span>rejectedCandidates</span><strong>{rejected}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'monitor_summary') {
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>health</span><strong>{String(details.health ?? '-')}</strong></div>
        <div className="kv-item"><span>readiness</span><strong>{String(details.readiness ?? '-')}</strong></div>
        <div className="kv-item"><span>reason</span><strong>{String(details.reason ?? '-')}</strong></div>
        <div className="kv-item"><span>mode</span><strong>{String(details.mode ?? '-')}</strong></div>
        <div className="kv-item"><span>wifiOk</span><strong>{String(details.wifiOk ?? '-')}</strong></div>
        <div className="kv-item"><span>bridgeOk</span><strong>{String(details.bridgeOk ?? '-')}</strong></div>
        <div className="kv-item"><span>cameraOk</span><strong>{String(details.cameraOk ?? '-')}</strong></div>
        <div className="kv-item"><span>audioOk</span><strong>{String(details.audioOk ?? '-')}</strong></div>
        <div className="kv-item"><span>uartOk</span><strong>{String(details.uartOk ?? '-')}</strong></div>
        <div className="kv-item"><span>batteryVoltage</span><strong>{String(details.batteryVoltage ?? '-')}</strong></div>
        <div className="kv-item"><span>leftRpm</span><strong>{String(details.leftRpm ?? '-')}</strong></div>
        <div className="kv-item"><span>rightRpm</span><strong>{String(details.rightRpm ?? '-')}</strong></div>
        <div className="kv-item"><span>controlSource</span><strong>{String(details.controlSource ?? '-')}</strong></div>
        <div className="kv-item"><span>lastQrcode</span><strong>{String(details.lastQrcode ?? '-')}</strong></div>
        <div className="kv-item"><span>lastVoiceCommand</span><strong>{String(details.lastVoiceCommand ?? '-')}</strong></div>
        <div className="kv-item"><span>lastFault</span><strong>{String(details.lastFault ?? '-')}</strong></div>
        <div className="kv-item"><span>snapshotCount</span><strong>{String(details.snapshotCount ?? '-')}</strong></div>
        <div className="kv-item"><span>reconnectCount</span><strong>{String(details.reconnectCount ?? '-')}</strong></div>
        <div className="kv-item"><span>protocolErrors</span><strong>{String(details.protocolErrors ?? '-')}</strong></div>
        <div className="kv-item"><span>recentSummary</span><strong>{String(details.recentSummary ?? '-')}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'monitor_diagnostics') {
    const systemStatus = details.systemStatus as Record<string, unknown> | undefined;
    const unhealthyComponents = Array.isArray(details.unhealthyComponents) ? details.unhealthyComponents.join(', ') : '-';
    const runtimeReasons = Array.isArray(details.runtimeReasons) ? details.runtimeReasons.join(', ') : '-';
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>componentStatusCount</span><strong>{String(details.componentStatusCount ?? '-')}</strong></div>
        <div className="kv-item"><span>unhealthyCount</span><strong>{String(details.unhealthyCount ?? '-')}</strong></div>
        <div className="kv-item"><span>unhealthyComponents</span><strong>{unhealthyComponents}</strong></div>
        <div className="kv-item"><span>systemStatus.name</span><strong>{String(systemStatus?.name ?? '-')}</strong></div>
        <div className="kv-item"><span>systemStatus.level</span><strong>{String(systemStatus?.level ?? '-')}</strong></div>
        <div className="kv-item"><span>systemStatus.message</span><strong>{String(systemStatus?.message ?? '-')}</strong></div>
        <div className="kv-item"><span>runtimeState</span><strong>{String(details.runtimeState ?? '-')}</strong></div>
        <div className="kv-item"><span>runtimeReasons</span><strong>{runtimeReasons}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'localization_summary') {
    const pose = details.pose as Record<string, unknown> | undefined;
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>feedbackAvailable</span><strong>{String(details.feedbackAvailable ?? '-')}</strong></div>
        <div className="kv-item"><span>stale</span><strong>{String(details.stale ?? '-')}</strong></div>
        <div className="kv-item"><span>pose.x</span><strong>{String(pose?.x ?? '-')}</strong></div>
        <div className="kv-item"><span>pose.y</span><strong>{String(pose?.y ?? '-')}</strong></div>
        <div className="kv-item"><span>pose.yaw</span><strong>{String(pose?.yaw ?? '-')}</strong></div>
        <div className="kv-item"><span>robotName</span><strong>{String(details.robotName ?? '-')}</strong></div>
        <div className="kv-item"><span>descriptionLoaded</span><strong>{String(details.descriptionLoaded ?? '-')}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'hardware_interface_summary') {
    const missing = Array.isArray(details.missing) ? details.missing.join(', ') : '-';
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>jointStateAvailable</span><strong>{String(details.jointStateAvailable ?? '-')}</strong></div>
        <div className="kv-item"><span>batteryStateAvailable</span><strong>{String(details.batteryStateAvailable ?? '-')}</strong></div>
        <div className="kv-item"><span>cmdObserved</span><strong>{String(details.cmdObserved ?? '-')}</strong></div>
        <div className="kv-item"><span>batteryPercent</span><strong>{String(details.batteryPercent ?? '-')}</strong></div>
        <div className="kv-item"><span>batteryVoltage</span><strong>{String(details.batteryVoltage ?? '-')}</strong></div>
        <div className="kv-item"><span>missing</span><strong>{missing}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'navigation_status') {
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>routeName</span><strong>{String(details.routeName ?? '-')}</strong></div>
        <div className="kv-item"><span>goal</span><strong>{String(details.goal ?? '-')}</strong></div>
        <div className="kv-item"><span>completedGoals</span><strong>{String(details.completedGoals ?? '-')}</strong></div>
        <div className="kv-item"><span>totalGoals</span><strong>{String(details.totalGoals ?? '-')}</strong></div>
        <div className="kv-item"><span>progress</span><strong>{String(details.progress ?? '-')}</strong></div>
        <div className="kv-item"><span>reason</span><strong>{String(details.reason ?? '-')}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'voice_ingress_health') {
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>state</span><strong>{String(details.state ?? '-')}</strong></div>
        <div className="kv-item"><span>reason</span><strong>{String(details.reason ?? '-')}</strong></div>
        <div className="kv-item"><span>required</span><strong>{String(details.required ?? '-')}</strong></div>
        <div className="kv-item"><span>expectedSourceId</span><strong>{String(details.expectedSourceId ?? '-')}</strong></div>
        <div className="kv-item"><span>lastSourceId</span><strong>{String(details.lastSourceId ?? '-')}</strong></div>
        <div className="kv-item"><span>lastCommand</span><strong>{String(details.lastCommand ?? '-')}</strong></div>
        <div className="kv-item"><span>lastConfidence</span><strong>{String(details.lastConfidence ?? '-')}</strong></div>
        <div className="kv-item"><span>lastIngressAgeSec</span><strong>{String(details.lastIngressAgeSec ?? '-')}</strong></div>
        <div className="kv-item"><span>timeoutSec</span><strong>{String(details.timeoutSec ?? '-')}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'navigation_path') {
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>poseCount</span><strong>{String(details.poseCount ?? '-')}</strong></div>
        <div className="kv-item"><span>hasPath</span><strong>{String(details.hasPath ?? '-')}</strong></div>
      </div>
    );
  }
  if (entry.kind === 'runtime_supervision') {
    const lifecycle = details.lifecycleManager as Record<string, unknown> | undefined;
    const bond = details.bondSupervision as Record<string, unknown> | undefined;
    const plan = details.recoveryPlan as Record<string, unknown> | undefined;
    const orchestrationComponents = details.orchestrationComponents as Record<string, Record<string, unknown>> | undefined;
    const orchestrationEntries = Object.entries(orchestrationComponents ?? {});
    const requiredComponentIds = orchestrationEntries
      .filter(([, item]) => Boolean(item?.requiredForMainline))
      .map(([componentId]) => componentId);
    const componentsMissingFields = orchestrationEntries
      .map(([componentId, item]) => {
        const missingFields = Array.isArray(item?.missingFields) ? item.missingFields : [];
        return missingFields.length ? `${componentId}:${missingFields.join('|')}` : null;
      })
      .filter((value): value is string => Boolean(value));
    const reasons = Array.isArray(details.reasons) ? details.reasons.join(', ') : '-';
    return (
      <div className="kv-grid">
        <div className="kv-item"><span>reasons</span><strong>{reasons}</strong></div>
        <div className="kv-item"><span>startupBarrierReady</span><strong>{String(details.startupBarrierReady ?? '-')}</strong></div>
        <div className="kv-item"><span>readiness</span><strong>{String(details.readiness ?? '-')}</strong></div>
        <div className="kv-item"><span>recoveryMode</span><strong>{String(details.recoveryMode ?? '-')}</strong></div>
        <div className="kv-item"><span>lifecycleManager.present</span><strong>{String(lifecycle?.present ?? '-')}</strong></div>
        <div className="kv-item"><span>lifecycleManager.type</span><strong>{String(lifecycle?.type ?? '-')}</strong></div>
        <div className="kv-item"><span>lifecycleManager.state</span><strong>{String(lifecycle?.state ?? '-')}</strong></div>
        <div className="kv-item"><span>lifecycleManager.managedNodes</span><strong>{JSON.stringify(lifecycle?.managedNodes ?? [])}</strong></div>
        <div className="kv-item"><span>lifecycleManager.recentTransitions</span><strong>{JSON.stringify(lifecycle?.recentTransitions ?? [])}</strong></div>
        <div className="kv-item"><span>bondSupervision.present</span><strong>{String(bond?.present ?? '-')}</strong></div>
        <div className="kv-item"><span>bondSupervision.type</span><strong>{String(bond?.type ?? '-')}</strong></div>
        <div className="kv-item"><span>bondSupervision.state</span><strong>{String(bond?.state ?? '-')}</strong></div>
        <div className="kv-item"><span>bondSupervision.managedNodes</span><strong>{JSON.stringify(bond?.managedNodes ?? [])}</strong></div>
        <div className="kv-item"><span>recoveryPlan.strategy</span><strong>{String(plan?.strategy ?? '-')}</strong></div>
        <div className="kv-item"><span>recoveryPlan.reason</span><strong>{String(plan?.reason ?? '-')}</strong></div>
        <div className="kv-item"><span>recoveryPlan.targetNodes</span><strong>{JSON.stringify(plan?.targetNodes ?? [])}</strong></div>
        <div className="kv-item"><span>orchestrationComponents</span><strong>{orchestrationEntries.length}</strong></div>
        <div className="kv-item"><span>orchestrationComponents.requiredForMainline</span><strong>{requiredComponentIds.join(', ') || '-'}</strong></div>
        <div className="kv-item"><span>orchestrationComponents.missingFields</span><strong>{componentsMissingFields.join(', ') || '-'}</strong></div>
      </div>
    );
  }
  return <pre className="code-block">{JSON.stringify(details, null, 2)}</pre>;
}

export function ReportSummaryPanel() {
  const logs = useRobotStore((state) => state.logs);
  const commands = useRobotStore((state) => state.commands);
  const history = useRobotStore((state) => state.history);
  const connection = useRobotStore((state) => state.connection);
  const runtime = useRobotStore((state) => state.runtime);
  const reports = useRobotStore((state) => state.reports);
  const exportStateSnapshot = useRobotStore((state) => state.exportStateSnapshot);

  const acked = commands.filter((item) => item.status === 'ack' || item.status === 'applied' || item.status === 'completed');
  const rejected = commands.filter((item) => item.status === 'rejected' || item.status === 'timeout' || item.status === 'denied' || item.status === 'cancelled');
  const criticalLogs = logs.filter((item) => item.level === 'ERROR' || item.level === 'CRITICAL');
  const summary = {
    protocolVersion: connection.protocolVersion,
    schemaVersion: connection.schemaVersion,
    compatibilityMode: connection.compatibilityMode,
    safetyPhase: runtime.safetyPhase,
    taskPhase: runtime.taskPhase,
    ackAvg: average(history.ackLatency),
    ackP95: percentile(history.ackLatency, 95),
    batteryMin: history.battery.length ? Math.min(...history.battery) : 0,
    frameDropMax: history.frameDrops.length ? Math.max(...history.frameDrops) : 0,
    commandStats: {
      total: commands.length,
      acked: acked.length,
      rejected: rejected.length,
      superseded: commands.filter((item) => item.status === 'superseded').length
    },
    criticalLogs: criticalLogs.length
  };

  return (
    <SectionCard
      title="会话摘要 / 导出"
      right={
        <div className="toolbar-inline">
          <FeatureMaturityPills featureIds={['observability.runtime_reports']} />
          <button className="ghost-btn small-btn" onClick={() => downloadText('session-summary.json', toJson(summary), 'application/json;charset=utf-8')}>
            <Download size={14} />摘要 JSON
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('session-commands.csv', exportCommandsAsCsv(commands), 'text/csv;charset=utf-8')}>
            <Download size={14} />命令 CSV
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('session-logs.csv', exportLogsAsCsv(logs), 'text/csv;charset=utf-8')}>
            <Download size={14} />日志 CSV
          </button>
          <button className="ghost-btn small-btn" onClick={() => downloadText('session-export.json', exportStateSnapshot().json, 'application/json;charset=utf-8')}>
            <Download size={14} />会话 JSON
          </button>
        </div>
      }
    >
      <div className="diff-box compact-box">
        <strong>导出边界</strong>
        <p className="muted">本面板导出的是前端会话级摘要与操作记录，适合回放和人工复盘；它不替代 release verification、acceptance report 或 evidence artifact。</p>
      </div>
      <div className="kv-grid">
        <div className="kv-item"><span>协议版本</span><strong>{connection.protocolVersion}</strong></div>
        <div className="kv-item"><span>Schema 版本</span><strong>{connection.schemaVersion}</strong></div>
        <div className="kv-item"><span>兼容层</span><strong>{connection.compatibilityMode}</strong></div>
        <div className="kv-item"><span>安全相位</span><strong>{runtime.safetyPhase}</strong></div>
        <div className="kv-item"><span>任务相位</span><strong>{runtime.taskPhase}</strong></div>
        <div className="kv-item"><span>ACK 平均</span><strong>{formatNumber(summary.ackAvg, 1)} ms</strong></div>
        <div className="kv-item"><span>ACK P95</span><strong>{formatNumber(summary.ackP95, 1)} ms</strong></div>
        <div className="kv-item"><span>最低电量</span><strong>{formatNumber(summary.batteryMin, 1)} %</strong></div>
        <div className="kv-item"><span>最大丢帧</span><strong>{summary.frameDropMax}</strong></div>
        <div className="kv-item"><span>关键日志</span><strong>{criticalLogs.length}</strong></div>
        <div className="kv-item"><span>ACK 成功</span><strong>{acked.length}/{commands.length || 0}</strong></div>
        <div className="kv-item"><span>异常命令</span><strong>{rejected.length}</strong></div>
      </div>

      <div className="diff-box compact-box">
        <strong>在线报告面</strong>
        <div className="kv-grid">
          {REPORT_ORDER.map(({ key, label }) => {
            const entry = reports[key as keyof typeof reports] as ReportSurfaceEntry | undefined;
            return (
              <div className="kv-item" key={key}>
                <span>{label}</span>
                <strong>{entry ? severityLabel(entry) : '未接入'}</strong>
              </div>
            );
          })}
        </div>
        {REPORT_ORDER.map(({ key, label }) => {
          const entry = reports[key as keyof typeof reports] as ReportSurfaceEntry | undefined;
          if (!entry) {
            return null;
          }
          return (
            <div className="diff-box compact-box" key={`detail-${key}`}>
              <strong>{label}</strong>
              <div className="kv-grid">
                <div className="kv-item"><span>kind</span><strong>{entry.kind ?? '-'}</strong></div>
                <div className="kv-item"><span>status</span><strong>{entry.status ?? '-'}</strong></div>
                <div className="kv-item"><span>summary</span><strong>{entry.summary ?? '-'}</strong></div>
                <div className="kv-item"><span>updatedAt</span><strong>{entry.updatedAt ?? '-'}</strong></div>
              </div>
              {renderTypedDetails(entry)}
            </div>
          );
        })}
      </div>
      <div className="diff-box compact-box">
        <strong>bridge capabilities</strong>
        <div className="tag-row">
          {connection.capabilities.map((cap) => (
            <span key={cap} className="tag-chip">{cap}</span>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}
