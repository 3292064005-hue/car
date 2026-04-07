import { HistoryPanel } from '@/components/HistoryPanel';
import { LogPanel } from '@/components/LogPanel';
import { ReportSummaryPanel } from '@/components/ReportSummaryPanel';

export default function ReportsPage() {
  return (
    <div className="page-stack two-column-page">
      <ReportSummaryPanel />
      <HistoryPanel />
      <LogPanel />
    </div>
  );
}
