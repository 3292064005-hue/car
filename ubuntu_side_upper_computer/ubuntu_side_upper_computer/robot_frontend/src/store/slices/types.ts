import type { StateCreator } from 'zustand';
import type { RobotStore } from '@/store/model';

export type RobotStoreSlice<T> = StateCreator<RobotStore, [], [], T>;
