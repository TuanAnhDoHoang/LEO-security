import { spawn, ChildProcess } from "child_process";
import { stripAnsi, detectLogType } from "./utils.js";
import type { BroadcastFn, SimulationState } from "./types.js";

type LineTransform = (raw: string, role: string) => {
  role: string;
  message: string;
  logType: string;
};

export class ProcessManager {
  private hpingProcess: ChildProcess | null = null;

  constructor(public readonly state: SimulationState, public readonly broadcast: BroadcastFn) {}

  public spawnCommand(
    command: string,
    args: string[],
    cwd: string,
    role: string,
    options: {
      prefix?: string;
      detached?: boolean;
      stdinData?: string;
      lineTransform?: LineTransform;
    } = {}
  ): ChildProcess {
    const proc = spawn(command, args, {
      cwd,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      detached: options.detached ?? true,
      stdio: [options.stdinData ? "pipe" : "pipe", "pipe", "pipe"],
    });

    this.state.processes.push(proc);

    const transform = options.lineTransform ?? ((rawLine: string, currentRole: string) => {
      return {
        role: currentRole,
        message: options.prefix ? `${options.prefix} ${stripAnsi(rawLine)}` : stripAnsi(rawLine),
        logType: detectLogType(rawLine),
      };
    });

    const handleData = (data: Buffer) => {
      const lines = data.toString().split("\n").filter((line) => line.trim());
      for (const line of lines) {
        const transformed = transform(line, role);
        if (!transformed.message) continue;
        this.broadcast({
          type: "log",
          role: transformed.role,
          message: transformed.message,
          logType: transformed.logType,
          timestamp: new Date().toISOString(),
        });
      }
    };

    proc.stdout?.on("data", handleData);
    proc.stderr?.on("data", handleData);

    if (options.stdinData && proc.stdin) {
      proc.stdin.write(options.stdinData);
      proc.stdin.end();
    }

    return proc;
  }

  public stopHping3(): void {
    if (!this.hpingProcess || !this.hpingProcess.pid) {
      this.broadcast({
        type: "log",
        role: "eavesdropper",
        message: "No active hping3 attack to stop.",
        logType: "warn",
        timestamp: new Date().toISOString(),
      });
      return;
    }

    this.broadcast({
      type: "log",
      role: "eavesdropper",
      message: "Stopping hping3 DDoS attack...",
      logType: "attack",
      timestamp: new Date().toISOString(),
    });

    try {
      process.kill(-this.hpingProcess.pid, "SIGTERM");
    } catch {
      // ignore
    }

    try {
      this.hpingProcess.kill("SIGTERM");
    } catch {
      // ignore
    }

    this.hpingProcess = null;
  }

  public killAllProcesses(): void {
    for (const proc of this.state.processes) {
      try {
        if (proc.pid) {
          process.kill(-proc.pid, "SIGTERM");
        }
      } catch {
        try {
          proc.kill("SIGTERM");
        } catch {
          // ignore
        }
      }
    }

    try {
      spawn("pkill", ["-f", "receiver.py"]);
      spawn("pkill", ["-f", "satellite.py"]);
      spawn("pkill", ["-f", "sender.py"]);
      spawn("pkill", ["-f", "eavesdropper.py"]);
    } catch {
      // ignore
    }

    this.state.processes = [];
    this.state.running = false;
    this.state.phase = "idle";
    this.hpingProcess = null;
  }

  public spawnHping3(): ChildProcess {
    const isRoot = process.getuid?.() === 0;
    const command = isRoot ? "hping3" : "sudo";
    const args = isRoot
      ? ["--udp", "--flood", "-d", "6500", "127.0.0.1", "-p", "9000"]
      : ["-S", "hping3", "--udp", "--flood", "-d", "6500", "127.0.0.1", "-p", "9000"];

    const proc = spawn(command, args, {
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (!isRoot && proc.stdin) {
      proc.stdin.write((process.env.SUDO_PASSWORD || "") + "\n");
      proc.stdin.end();
    }

    this.state.processes.push(proc);
    this.hpingProcess = proc;

    const handleData = (data: Buffer) => {
      const lines = data.toString().split("\n").filter((line) => line.trim());
      for (const line of lines) {
        if (line.includes("[sudo]") || line.includes("password for")) {
          continue;
        }
        this.broadcast({
          type: "log",
          role: "eavesdropper",
          message: `[hping3] ${stripAnsi(line)}`,
          logType: "attack",
          timestamp: new Date().toISOString(),
        });
      }
    };

    proc.stdout?.on("data", handleData);
    proc.stderr?.on("data", handleData);

    proc.on("close", (code) => {
      if (this.hpingProcess === proc) {
        this.hpingProcess = null;
      }
      this.broadcast({
        type: "log",
        role: "eavesdropper",
        message: `hping3 attack stopped (exit code: ${code})`,
        logType: "info",
        timestamp: new Date().toISOString(),
      });
    });

    proc.on("error", (err) => {
      this.broadcast({
        type: "log",
        role: "eavesdropper",
        message: `hping3 error: ${err.message}`,
        logType: "attack",
        timestamp: new Date().toISOString(),
      });
    });

    return proc;
  }
}
