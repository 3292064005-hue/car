import { useState } from 'react';
import { robotBridge } from '@/bridge/client';
import { SectionCard } from '@/components/SectionCard';
import { deepCloneParams, safeClipboardWrite, summarizeParamDiff, toJson } from '@/shared/utils';
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
  const selectedProfile = profiles.profiles[profiles.activeProfileName] ? deepCloneParams(profiles.profiles[profiles.activeProfileName]) : null;
  const selectedProfileDiff = selectedProfile ? summarizeParamDiff(profiles.applied, selectedProfile) : [];

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
          className="ghost-btn"
          disabled={ui.demoReadonly || !selectedProfile || selectedProfileDiff.length === 0}
          onClick={() => robotBridge.send('apply_param_profile', { profileName: profiles.activeProfileName, source: 'frontend' }, `应用运行参数预设 ${profiles.activeProfileName}`)}
        >
          应用当前预设
        </button>
        <button
          className="primary-btn"
          disabled={ui.demoReadonly || diff.length === 0}
          onClick={() => {
            applyDraftParams();
            robotBridge.send('apply_param_draft', { params: deepCloneParams(profiles.draft), source: 'frontend' }, `应用运行参数草稿 (${diff.length} 项变更)`);
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
        <strong>应用语义</strong>
        <p className="muted">下拉选择只负责把预设加载到草稿；“应用当前预设”会触发一次 profile 事务；“应用草稿”会把整组草稿作为一次批量事务提交到 bridge。</p>
      </div>

      <div className="diff-box">
        <strong>草稿差异</strong>
        {diff.length === 0 ? <p className="muted">草稿与当前 applied 一致。</p> : null}
        {diff.map((line) => (
          <div key={line} className="history-list-item"><span>{line}</span></div>
        ))}
        <div className="history-list-item"><span>configDigest: {profiles.configDigest ?? '未同步'}</span></div>
        <div className="history-list-item"><span>runtimeParamVersion: {profiles.runtimeParamVersion}</span></div>
        <div className="history-list-item"><span>projectionState: {profiles.projectionState}</span></div>
        <div className="history-list-item"><span>committedConfigDigest: {profiles.committedConfigDigest ?? '未同步'}</span></div>
        <div className="history-list-item"><span>committedProfileName: {profiles.committedProfileName}</span></div>
        <div className="history-list-item"><span>committedRuntimeParamVersion: {profiles.committedRuntimeParamVersion}</span></div>
        {profiles.lastParamApplyResult?.message ? (
          <div className="history-list-item"><span>最近结果: {profiles.lastParamApplyResult.message}</span></div>
        ) : null}
      </div>
    </SectionCard>
  );
}
