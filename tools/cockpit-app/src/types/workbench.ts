/**
 * Workbench-level types. These describe the parent 1C AI Workbench
 * project surface that the Cockpit orchestrates.
 */
export interface WorkbenchProject {
  name: string;
  version: string;
  root: string;
  docs: {
    opencode: string;
    commercialKit: string;
    startHere: string;
  };
}

export interface DumpInfo {
  path: string;
  fileCount: number;
  totalSize: number;
  lastScannedAt: string | null;
}

export type RiskSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface RiskFinding {
  id: string;
  severity: RiskSeverity;
  category: string;
  title: string;
  message: string;
  objectRef: string | null;
  file: string | null;
  confidence: number;
}

export interface HelpTopic {
  id: number;
  parentId: number | null;
  title: string;
  level: number;
}
