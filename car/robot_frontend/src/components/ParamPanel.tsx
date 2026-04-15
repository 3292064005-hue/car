import { useMemo, useState } from 'react';
import { robotBridge } from '@/bridge/client';
import { SectionCard } from '@/components/SectionCard';
import { deepCloneParams, safeClipboardWrite, summarizeParamDiff, toJson } from '@/shared/utils';
import {
  BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS,
  FRONTEND_LOCAL_RUNTIME_PARAM_KEYS,
  diffRuntimeParamPatch,
} from '@/shared/runtimeParamModel';
import { useRobotStore } from '@/store/useRobotStore';
import type { ParamProfile, ParamProfileScope } from '@/types/robot';

const LABELS: Record<keyof ParamProfile, string> = {
  maxLinearSpeed: '最大线速度',
  maxAngularSpeed: '最大角速度',
  teleopStep: '手动调节步长',
  trackOffsetDeadband: '跟踪死区',
  lowPowerThreshold: '低电量阈值',
  reconnectTimeoutMs: '重连超时(ms)'
};

function scopeLabel(scope: ParamProfileScope): string {
  return scope === 'local' ? '本地预设' : '运行时预设';
}

function ParamInputs({ keys, values, onChange }: { keys: Array<keyof ParamProfile>; values: ParamProfile; onChange: (key: keyof ParamProfile, value: number) => void }) {
  return (
    <div className="param-grid">
      {keys.map((key) => (
        <label className="param-item" key={key}>
          <span>{LABELS[key]}</span>
          <input type="number" step="0.01" value={values[key]} onChange={(event) => onChange(key, Number(event.target.value))} />
        </label>
      ))}
    </div>
  );
}

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
  const draftPatch = diffRuntimeParamPatch(profiles.applied, profiles.draft);
  const activeProfileScope = profiles.profileScopes[profiles.activeProfileName] ?? 'runtime';
  const selectedProfile = profiles.profiles[profiles.activeProfileName] ? deepCloneParams(profiles.profiles[profiles.activeProfileName]) : null;
  const selectedProfileDiff = selectedProfile ? summarizeParamDiff(profiles.applied, selectedProfile) : [];
  const selectedProfilePatch = selectedProfile ? diffRuntimeParamPatch(profiles.applied, selectedProfile) : null;
  const groupedProfileNames = useMemo(() => {
    const runtime: string[] = [];
    const local: string[] = [];
    for (const name of Object.keys(profiles.profiles)) {
      if ((profiles.profileScopes[name] ?? 'runtime') === 'local') {
        local.push(name);
      } else {
        runtime.push(name);
      }
    }
    return { runtime, local };
  }, [profiles.profiles, profiles.profileScopes]);

  return (
    <SectionCard title="运行参数">
      <div className="diff-box">
        <strong>后端权威参数</strong>
        <p className="muted">这些字段进入 bridge 事务，并等待 control / decision / monitor 等消费者 ACK 后才会从 provisional 变为 committed。</p>
        <ParamInputs keys={BACKEND_AUTHORITATIVE_RUNTIME_PARAM_KEYS} values={profiles.draft} onChange={setDraftParam} />
      </div>

      <div className="diff-box">
        <strong>浏览器本地参数</strong>
        <p className="muted">这些字段不会进入 backend_authoritative 事务，只保存在当前浏览器并影响本地 UI / transport 行为。</p>
        <ParamInputs keys={FRONTEND_LOCAL_RUNTIME_PARAM_KEYS} values={profiles.draft} onChange={setDraftParam} />
      </div>

      <div className="inline-actions wrap-start">
        <select className="input-small" value={profiles.activeProfileName} onChange={(event) => applyProfile(event.target.value)}>
          <optgroup label="运行时预设">
            {groupedProfileNames.runtime.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </optgroup>
          {groupedProfileNames.local.length > 0 ? (
            <optgroup label="本地预设（仅浏览器）">
              {groupedProfileNames.local.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </optgroup>
          ) : null}
        </select>
        <button className="ghost-btn" onClick={resetDraftToApplied}>重置草稿</button>
        <button
          className="ghost-btn"
          disabled={ui.demoReadonly || activeProfileScope !== 'runtime' || !selectedProfilePatch || selectedProfilePatch.authoritativeKeys.length === 0}
          onClick={() => robotBridge.send('apply_param_profile', { profileName: profiles.activeProfileName, source: 'frontend' }, `应用运行时参数预设 ${profiles.activeProfileName}`)}
        >
          应用运行时预设
        </button>
        <button
          className="primary-btn"
          disabled={ui.demoReadonly || diff.length === 0}
          onClick={() => {
            applyDraftParams();
            if (draftPatch.authoritativeKeys.length > 0) {
              robotBridge.send(
                'apply_param_draft',
                { params: draftPatch.authoritativePatch, source: 'frontend' },
                `应用运行参数草稿 (${draftPatch.authoritativeKeys.length} 项权威变更)`,
              );
            }
          }}
        >
          应用草稿
        </button>
      </div>

      <div className="inline-actions wrap-start">
        <input className="input-small" placeholder="新本地预设名称" value={profileName} onChange={(event) => setProfileName(event.target.value)} />
        <button className="ghost-btn" onClick={() => saveCurrentAsProfile(profileName)}>保存为本地预设</button>
        <button className="ghost-btn" onClick={() => safeClipboardWrite(toJson(profiles))}>复制参数 JSON</button>
      </div>

      <div className="diff-box">
        <strong>应用语义</strong>
        <p className="muted">下拉选择只负责把预设加载到草稿；“应用运行时预设”只提交后端权威字段；“应用草稿”会先把本地字段写入浏览器，再仅将权威字段作为一次批量事务提交到 bridge；“保存为本地预设”只持久化到当前浏览器。</p>
      </div>

      <div className="diff-box">
        <strong>预设状态</strong>
        <div className="history-list-item"><span>当前选中: {profiles.activeProfileName}（{scopeLabel(activeProfileScope)}）</span></div>
        <div className="history-list-item"><span>最近已提交运行时预设: {profiles.committedProfileName}</span></div>
        {activeProfileScope === 'local' ? (
          <div className="history-list-item"><span>提示：本地预设只能先加载到草稿，再通过“应用草稿”提交本地字段 / 权威字段各自的作用域。</span></div>
        ) : null}
      </div>

      <div className="diff-box">
        <strong>草稿差异</strong>
        {diff.length === 0 ? <p className="muted">草稿与当前 applied 一致。</p> : null}
        {diff.map((line) => (
          <div key={line} className="history-list-item"><span>{line}</span></div>
        ))}
        <div className="history-list-item"><span>backend_authoritative: {draftPatch.authoritativeKeys.length ? draftPatch.authoritativeKeys.join(', ') : '无'}</span></div>
        <div className="history-list-item"><span>frontend_local: {draftPatch.frontendLocalKeys.length ? draftPatch.frontendLocalKeys.join(', ') : '无'}</span></div>
        <div className="history-list-item"><span>selectedProfile backend_authoritative: {selectedProfilePatch?.authoritativeKeys.length ? selectedProfilePatch.authoritativeKeys.join(', ') : '无'}</span></div>
        <div className="history-list-item"><span>selectedProfile frontend_local: {selectedProfilePatch?.frontendLocalKeys.length ? selectedProfilePatch.frontendLocalKeys.join(', ') : '无'}</span></div>
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
