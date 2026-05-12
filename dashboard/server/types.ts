import type { ChildProcess } from "child_process";

export type LogType = "attack" | "warn" | "secure" | "info";
export type LogRole = "sender" | "receiver" | "eavesdropper" | "system" | "attack";

export interface SimulationState {
  processes: ChildProcess[];
  running: boolean;
  phase: string;
}

export type BroadcastFn = (data: Record<string, unknown>) => void;
