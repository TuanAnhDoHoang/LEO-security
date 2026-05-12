export function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, "").replace(/\x1b\[[\d;]*[A-Za-z]/g, "");
}

export function detectLogType(raw: string): string {
  if (raw.includes("\x1b[91m") || raw.includes("REPLAY REJECTED") || raw.includes("THẤT BẠI") || raw.includes("GCM TAG") || raw.includes("tamper")) return "attack";
  if (raw.includes("\x1b[92m") || raw.includes("✓") || raw.includes("hoàn tất") || raw.includes("DECRYPT")) return "secure";
  if (raw.includes("\x1b[93m") || raw.includes("WARNING") || raw.includes("PLAIN") || raw.includes("⚠") || raw.includes("lộ")) return "warn";
  return "info";
}

export function ddosDetectLogType(avgIntervalMs: number): string {
  if (avgIntervalMs < 1.0) return "attack";
  if (avgIntervalMs < 10.0) return "warn";
  return "secure";
}

export function parseAvgInterval(line: string): number | null {
  const match = line.match(/avg_interval=([\d.]+)ms/);
  return match ? parseFloat(match[1]) : null;
}
