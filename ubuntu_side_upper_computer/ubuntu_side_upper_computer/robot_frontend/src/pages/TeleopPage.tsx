import { ChassisPanel } from '@/components/ChassisPanel';
import { CommandQueuePanel } from '@/components/CommandQueuePanel';
import { ConnectionPanel } from '@/components/ConnectionPanel';
import { FaultPanel } from '@/components/FaultPanel';
import { TeleopPanel } from '@/components/TeleopPanel';

export default function TeleopPage() {
  return (
    <div className="two-column-page">
      <div>
        <TeleopPanel />
        <ChassisPanel />
      </div>
      <div>
        <ConnectionPanel />
        <CommandQueuePanel />
        <FaultPanel />
      </div>
    </div>
  );
}
