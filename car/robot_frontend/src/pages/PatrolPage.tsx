import { CommandQueuePanel } from '@/components/CommandQueuePanel';
import { LogPanel } from '@/components/LogPanel';
import { PatrolPanel } from '@/components/PatrolPanel';
import { VideoPanel } from '@/components/VideoPanel';
import { VisionPanel } from '@/components/VisionPanel';

export default function PatrolPage() {
  return (
    <div className="two-column-page wide-left">
      <div>
        <PatrolPanel />
        <VideoPanel />
      </div>
      <div>
        <CommandQueuePanel />
        <VisionPanel />
        <LogPanel />
      </div>
    </div>
  );
}
