import { CommandQueuePanel } from '@/components/CommandQueuePanel';
import { ConnectionPanel } from '@/components/ConnectionPanel';
import { FaultPanel } from '@/components/FaultPanel';
import { ParamPanel } from '@/components/ParamPanel';
import { PowerPanel } from '@/components/PowerPanel';

export default function SafetyPage() {
  return (
    <div className="two-column-page">
      <div>
        <FaultPanel />
        <PowerPanel />
        <ConnectionPanel />
      </div>
      <div>
        <ParamPanel />
        <CommandQueuePanel />
      </div>
    </div>
  );
}
