import { buildSessionExport } from '@/shared/utils';
import type { RobotStore } from '@/store/model';

export function createExportSlice(get: () => RobotStore): Pick<RobotStore, 'exportStateSnapshot'> {
  return {
    exportStateSnapshot: () => {
      const logs = get().logs;
      const history = get().history;
      const params = get().profiles;
      const inspectorTrace = get().inspector.trace;
      const commands = get().commands;
      return {
        logs,
        history,
        params,
        inspectorTrace,
        commands,
        json: buildSessionExport(logs, history, params, inspectorTrace, commands),
      };
    },
  };
}
