import { SectionCard } from '@/components/SectionCard';
import { StatusPill } from '@/components/StatusPill';
import { formatTimestamp } from '@/shared/utils';
import { useRobotStore } from '@/store/useRobotStore';

export function VideoPanel() {
  const vision = useRobotStore((state) => state.vision);
  const connection = useRobotStore((state) => state.connection);

  const showOverlay = !connection.videoConnected || connection.staleVision;

  return (
    <SectionCard
      title="视频主视图"
      right={<StatusPill label={showOverlay ? '断流/过期' : '在线流'} tone={showOverlay ? 'danger' : 'success'} />}
    >
      <div className="video-shell">
        <img className="video-frame" src={vision.streamUrl} alt="Robot MJPEG Stream" />
        {showOverlay ? <div className="video-overlay">视频流异常或视觉数据过期</div> : null}
      </div>
      <div className="video-meta">
        <span>目标：{vision.targetType ?? '--'}</span>
        <span>二维码：{vision.qrcodeText ?? '--'}</span>
        <span>最新检测：{formatTimestamp(vision.detectTimestamp)}</span>
      </div>
    </SectionCard>
  );
}
