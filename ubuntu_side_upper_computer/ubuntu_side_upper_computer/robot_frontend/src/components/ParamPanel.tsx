import { useState } from 'react';
import { robotBridge } from '@/bridge/client';
import { SectionCard } from '@/components/SectionCard';
import { safeClipboardWrite, summarizeParamDiff, toJson } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';
import type { ParamProfile } from '@/types/robot';

const LABELS: Record<keyof ParamProfile, string> = {
  maxLinearSpeed: '最大线速度',
  maxAngularSpeed: '最大角速度',
  teleopStep: '手动调节步长',
  trackOffsetDeadband: '跟踪死区',
  lowPowerThreshold: '低电量阈值',
  reconnectTimeoutMs: '重连超时(ms)'
};

export function ParamPanel() {
  const profiles = useRobotStore((state) => state.profiles);
  const setDraftParam = useRobotStore((state) => state.setDraftParam);
  const resetDraftToApplied = useRobotStore((state) => state.resetDraftToApplied);
  const applyDraftParams = useRobotStore((state) => state.applyDraftParams);
  const applyProfile = useRobotStore((state) => state.applyProfile);
  const saveCurrentAsProfile = useRobotStore((state) => state.saveCurrentAsProfile);
  const ui = useRobotStore((state) => state.ui);
  const [profileName, setProfileName] = useState('');

  const diff = summarizeParamDiff(profiles.applied, profiles.draft);

  return (
    <SectionCard title="运行参数">
      <div className="param-grid">
        {Object.entries(profiles.draft).map(([key, value]) => (
          <label className="param-item" key={key}>
            <span>{LABELS[key as keyof ParamProfile]}</span>
            <input type="number" step="0.01" value={value} onChange={(event) => setDraftParam(key as keyof ParamProfile, Number(event.target.value))} />
          </label>
        ))}
      </div>

      <div className="inline-actions wrap-start">
        <select className="input-small" value={profiles.activeProfileName} onChange={(event) => applyProfile(event.target.value)}>
          {Object.keys(profiles.profiles).map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <button className="ghost-btn" onClick={resetDraftToApplied}>重置草稿</button>
        <button
          className="primary-btn"
          disabled={ui.demoReadonly || diff.length === 0}
          onClick={() => {
            applyDraftParams();
            (Object.keys(profiles.draft) as Array<keyof ParamProfile>).forEach((key) => {
              if (profiles.applied[key] !== profiles.draft[key]) {
                robotBridge.send('set_param', { key, value: profiles.draft[key], source: 'frontend' }, `更新参数 ${key}`);
              }
            });
          }}
        >
          应用草稿
        </button>
      </div>

      <div className="inline-actions wrap-start">
        <input className="input-small" placeholder="新配置名称" value={profileName} onChange={(event) => setProfileName(event.target.value)} />
        <button className="ghost-btn" onClick={() => profileName.trim() && saveCurrentAsProfile(profileName.trim())}>保存为新配置</button>
        <button className="ghost-btn" onClick={() => safeClipboardWrite(toJson(profiles))}>复制参数 JSON</button>
      </div>

      <div className="diff-box">
        <strong>草稿差异</strong>
        {diff.length === 0 ? <p className="muted">草稿与当前 applied 一致。</p> : null}
        {diff.map((line) => (
          <div key={line} className="history-list-item"><span>{line}</span></div>
        ))}
        <div className="history-list-item"><span>configDigest: {profiles.configDigest ?? '未同步'}</span></div>
        <div className="history-list-item"><span>runtimeParamVersion: {profiles.runtimeParamVersion}</span></div>
        {profiles.lastParamApplyResult?.message ? (
          <div className="history-list-item"><span>最近结果: {profiles.lastParamApplyResult.message}</span></div>
        ) : null}
      </div>
    </SectionCard>
  );
}
