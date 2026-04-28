import { robotBridge } from '@/bridge/client';
import { commandButtonState } from '@/bridge/commandPolicy';
import { FeatureMaturityPills } from '@/components/FeatureMaturityPills';
import { KeyValueGrid } from '@/components/KeyValueGrid';
import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function VoicePanel() {
  const voice = useRobotStore((state) => state.voice);
  const normalSpeakState = commandButtonState('speak_fixed_text', { text: '系统状态正常', source: 'frontend' });
  const alertSpeakState = commandButtonState('speak_fixed_text', { text: '检测到异常，请注意', source: 'frontend' });

  return (
    <SectionCard title="语音状态" right={<div className="toolbar-inline"><FeatureMaturityPills featureIds={['operator.voice_fixed_text']} /><StatusPill label={voice.speaking ? '播报中' : '空闲'} tone={voice.speaking ? 'warning' : 'success'} /></div>}>
      <KeyValueGrid
        items={[
          { label: '最近命令', value: voice.lastVoiceCommand ?? '--', emphasis: Boolean(voice.lastVoiceCommand) },
          { label: '置信度', value: `${voice.voiceConfidence.toFixed(2)}` },
          { label: '唤醒状态', value: voice.wakeStatus },
          { label: '最近播报', value: voice.lastSpeakText ?? '--' },
          { label: '最近更新', value: formatTimestamp(voice.lastUpdateAt) }
        ]}
      />
      <div className="inline-actions">
        <button className="ghost-btn" title={normalSpeakState.reason} disabled={normalSpeakState.disabled} onClick={() => robotBridge.send('speak_fixed_text', { text: '系统状态正常', source: 'frontend' }, '播报状态正常')}>
          播报状态正常
        </button>
        <button className="ghost-btn" title={alertSpeakState.reason} disabled={alertSpeakState.disabled} onClick={() => robotBridge.send('speak_fixed_text', { text: '检测到异常，请注意', source: 'frontend' }, '播报异常提醒')}>
          播报异常提醒
        </button>
      </div>
      <div className="history-list">
        <span className="section-meta-title">最近语音事件</span>
        {voice.recentCommands.length === 0 ? <p className="muted">暂无语音事件。</p> : null}
        {voice.recentCommands.map((item) => (
          <div className="history-list-item" key={item.id}>
            <div>
              <strong>{item.command}</strong>
              <span className="muted"> 置信度 {item.confidence.toFixed(2)}</span>
            </div>
            <span>{formatTimestamp(item.ts)}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
