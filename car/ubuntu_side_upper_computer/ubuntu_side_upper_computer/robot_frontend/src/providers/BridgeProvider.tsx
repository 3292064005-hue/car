import { useEffect, type PropsWithChildren } from 'react';
import { robotBridge } from '@/bridge/client';
import { useRobotStore } from '@/store/useRobotStore';

export function BridgeProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    robotBridge.connect();
    const timer = window.setInterval(() => {
      useRobotStore.getState().tickRuntime();
    }, 500);
    return () => {
      window.clearInterval(timer);
      robotBridge.disconnect();
    };
  }, []);

  return <>{children}</>;
}
