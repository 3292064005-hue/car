import { LogPanel } from '@/components/LogPanel';
import { VideoPanel } from '@/components/VideoPanel';
import { VisionPanel } from '@/components/VisionPanel';
import { VoicePanel } from '@/components/VoicePanel';

export default function PerceptionPage() {
  return (
    <div className="two-column-page wide-left">
      <div>
        <VideoPanel />
        <VisionPanel />
      </div>
      <div>
        <VoicePanel />
        <LogPanel />
      </div>
    </div>
  );
}
