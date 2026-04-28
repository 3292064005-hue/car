import { HistoryPanel } from '@/components/HistoryPanel';
import { LaneLifecyclePanel } from '@/components/LaneLifecyclePanel';
import { LogPanel } from '@/components/LogPanel';
import { ReportSummaryPanel } from '@/components/ReportSummaryPanel';

export default function ReportsPage() {
  return (
    <div className="page-stack two-column-page">
      <ReportSummaryPanel />
      <LaneLifecyclePanel />
      <HistoryPanel />
      <LogPanel />
    </div>
  );
}
