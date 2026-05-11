/**
 * server/index.ts — Backend for LEO Security Dashboard
 * Spawns Python simulation processes and streams stdout/stderr
 * to connected WebSocket clients in real-time.
 */

import express from "express";
import http from "http";
import { WebSocketServer, WebSocket } from "ws";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import cors from "cors";

import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3001;
const EAVESDROPPER_DIR = path.resolve(__dirname, "../../eavesdropper");
const DDOS_DIR = path.resolve(__dirname, "../../ddos/LEO");


const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// Track active simulation processes
interface SimulationState {
  processes: ChildProcess[];
  running: boolean;
  phase: string;
}

let simulation: SimulationState = {
  processes: [],
  running: false,
  phase: "idle",
};

function broadcast(data: object) {
  const msg = JSON.stringify(data);
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  });
}

/**
 * Strip ANSI escape codes from text for clean display
 */
function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, "").replace(/\x1b\[[\d;]*[A-Za-z]/g, "");
}

/**
 * Parse the ANSI color codes to determine the "role" color class
 */
function detectLogType(raw: string): string {
  if (raw.includes("\x1b[91m") || raw.includes("REPLAY REJECTED") || raw.includes("THẤT BẠI") || raw.includes("GCM TAG") || raw.includes("tamper")) return "attack";
  if (raw.includes("\x1b[92m") || raw.includes("✓") || raw.includes("hoàn tất") || raw.includes("DECRYPT")) return "secure";
  if (raw.includes("\x1b[93m") || raw.includes("WARNING") || raw.includes("PLAIN") || raw.includes("⚠") || raw.includes("lộ")) return "warn";
  return "info";
}

function ddosDetectLogType(avgIntervalMs: number) {
  if (avgIntervalMs < 1.0)  return "attack";     // < 1ms   → TẤN CÔNG
  if (avgIntervalMs < 10.0) return "warn";  // < 10ms  → CẢNH BÁO
  return "secure";                             // ≥ 10ms  → BÌNH THƯỜNG
}

function killAllProcesses() {
  simulation.processes.forEach((proc) => {
    try {
      if (proc.pid) {
        process.kill(-proc.pid, "SIGTERM");
      }
    } catch {
      try {
        proc.kill("SIGTERM");
      } catch {
        // Already dead
      }
    }
  });

  // Aggressive cleanup of orphaned simulation scripts
  try {
    spawn("pkill", ["-f", "receiver.py"]);
    spawn("pkill", ["-f", "satellite.py"]);
    spawn("pkill", ["-f", "sender.py"]);
    spawn("pkill", ["-f", "eavesdropper.py"]);
  } catch {
    // Ignore pkill errors
  }

  simulation.processes = [];
  simulation.running = false;
  simulation.phase = "idle";
}
/**
 * Run the eavesdropper demo using run_demo.py's inline components approach
 * but as 3 separate visible processes for the dashboard.
 * 
 * We use a wrapper script approach: spawn run_demo.py which handles everything
 * internally, but we also spawn the individual scripts for visual separation.
 * 
 * Actually, for the dashboard we'll run a custom orchestrator that spawns
 * sender, receiver, satellite, and eavesdropper as separate processes
 * and tags their output.
 */
function spawnScript(scriptName: string, args: string[], role: string) {
  const proc = spawn("python3", [scriptName, ...args], {
    cwd: EAVESDROPPER_DIR,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    detached: true,
  });

  simulation.processes.push(proc);

  const handleData = (data: Buffer) => {
    const lines = data.toString().split("\n").filter((l: string) => l.trim());
    for (const line of lines) {
      let roleToUse = role;
      let cleanLine = stripAnsi(line);

      // If the line already has a tag (from --dashboard flag), use it
      if (cleanLine.startsWith("[SENDER]")) {
        roleToUse = "sender";
        cleanLine = cleanLine.replace("[SENDER] ", "");
      } else if (cleanLine.startsWith("[RECEIVER]")) {
        roleToUse = "receiver";
        cleanLine = cleanLine.replace("[RECEIVER] ", "");
      } else if (cleanLine.startsWith("[EAVESDROPPER]")) {
        roleToUse = "eavesdropper";
        cleanLine = cleanLine.replace("[EAVESDROPPER] ", "");
      } else if (cleanLine.startsWith("[SAT-A]") || cleanLine.startsWith("[SAT-B]") || cleanLine.startsWith("[SAT-C]")) {
        roleToUse = "system";
      }

      const logType = detectLogType(line);

      broadcast({
        type: "log",
        role: roleToUse,
        message: cleanLine,
        logType,
        timestamp: new Date().toISOString(),
      });
    }
  };

  proc.stdout?.on("data", handleData);
  proc.stderr?.on("data", handleData);

  return proc;
}

async function startEavesdropperDemo(mode: string = "plain") {
  // Unconditionally kill any existing session to prevent "already running" lockouts
  killAllProcesses();

  simulation.running = true;
  simulation.phase = `eavesdropper-${mode}`;

  broadcast({
    type: "status",
    status: "starting",
    phase: simulation.phase,
    message: `Starting individual eavesdropper components (${mode})...`,
  });

  try {
    // 1. Receiver & Key Server
    spawnScript("receiver.py", ["--local", "--dashboard"], "receiver");

    // 2. Satellite C (near receiver)
    spawnScript("satellite.py", ["sat-c", "--local", "--dashboard"], "system");

    // 3. Satellite B (middle relay)
    spawnScript("satellite.py", ["sat-b", "--local", "--dashboard"], "system");

    // 4. Eavesdropper (Passive Monitor)
    spawnScript("eavesdropper.py", ["--local", "--dashboard"], "eavesdropper");

    // 5. Satellite A (near sender)
    spawnScript("satellite.py", ["sat-a", "--local", "--dashboard"], "system");

    // Wait for servers to bind
    await new Promise(resolve => setTimeout(resolve, 1500));

    // 5. Sender (client)
    const senderProc = spawnScript("sender.py", [mode, "--local", "--dashboard"], "sender");

    senderProc.on("close", (code) => {
      simulation.running = false;
      broadcast({
        type: "status",
        status: "stopped",
        message: `Simulation finished (sender exit code: ${code})`,
      });
    });

  } catch (err: any) {
    simulation.running = false;
    broadcast({
      type: "error",
      message: `Failed to start simulation: ${err.message}`,
    });
  }
}

function ddosSpawnScript(scriptName: string, args: string[], role: string) {
  const proc = spawn("python3", [scriptName, ...args], {
    cwd: DDOS_DIR,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    detached: true,
  });

  simulation.processes.push(proc);

  const handleData = (data: Buffer) => {
    const lines = data.toString().split("\n").filter((l: string) => l.trim());
    for (const line of lines) {
      let roleToUse = role;
      let cleanLine = stripAnsi(line);

      // If the line already has a tag (from --dashboard flag), use it
      if (cleanLine.startsWith("[SENDER]")) {
        roleToUse = "sender";
        cleanLine = cleanLine.replace("[SENDER] ", "");
      } else if (cleanLine.startsWith("[RECEIVER]")) {
        roleToUse = "receiver";
        cleanLine = cleanLine.replace("[RECEIVER] ", "");
      } else if (cleanLine.startsWith("[SATELLITE]")) {
        roleToUse = "system";
      }

      if (roleToUse === "receiver") {
        const intervalMatch = cleanLine.match(/avg_interval=([\d.]+)ms/);
        if (intervalMatch) {
          const avgIntervalMs = parseFloat(intervalMatch[1]);
          console.log("avg_interval:", avgIntervalMs, "ms");

          const logType = ddosDetectLogType(avgIntervalMs);
          broadcast({
            type: "log",
            role: roleToUse,
            message: cleanLine,
            logType,
            timestamp: new Date().toISOString(),
          });
        } else {
          // Broadcast receiver logs even if they don't contain avg_interval
          const logType = detectLogType(line);
          broadcast({
            type: "log",
            role: roleToUse,
            message: cleanLine,
            logType,
            timestamp: new Date().toISOString(),
          });
        }
      } else {
        // Broadcast logs from sender and system
        const logType = detectLogType(line);
        broadcast({
          type: "log",
          role: roleToUse,
          message: cleanLine,
          logType,
          timestamp: new Date().toISOString(),
        });
      }
    }
  };

  proc.stdout?.on("data", handleData);
  proc.stderr?.on("data", handleData);

  return proc;
}

async function startDdosDemo(mode: string) {
  // Unconditionally kill any existing session to prevent "already running" lockouts
  killAllProcesses();

  simulation.running = true;
  simulation.phase = `ddos-${mode}`;

  broadcast({
    type: "status",
    status: "starting",
    phase: simulation.phase,
    message: `Starting individual ddos components (${mode})...`,
  });

  console.log("Broad cast successly");

  try {
    // 1. Receiver & Key Server
    ddosSpawnScript("receiver.py", ["--local"], "receiver");

    // 2. Satellite C (near receiver)
    ddosSpawnScript("satellite.py", ["127.0.0.1", "127.0.0.1", "9000", "9001"], "system");

    // 3. Satellite B (middle relay)
    ddosSpawnScript("satellite.py", ["127.0.0.1", "127.0.0.1", "9001", "9002"], "system");

    // Wait for servers to bind
    await new Promise(resolve => setTimeout(resolve, 1500));

    // 5. Sender (client)
    const senderProc = ddosSpawnScript("sender.py", [mode, "--local"], "sender");

    senderProc.on("close", (code) => {
      simulation.running = false;
      broadcast({
        type: "status",
        status: "stopped",
        message: `Simulation finished (sender exit code: ${code})`,
      });
    });

  } catch (err: any) {
    simulation.running = false;
    broadcast({
      type: "error",
      message: `Failed to start simulation: ${err.message}`,
    });
  }
}

function startHping3() {
  console.log("🔨 Starting hping3 DDoS attack...");
  broadcast({
    type: "log",
    role: "eavesdropper",
    message: "Starting hping3 DDoS attack: --udp --flood -d 6500 127.0.0.1 -p 9000",
    logType: "attack",
    timestamp: new Date().toISOString(),
  });

  const isRoot = process.getuid?.() === 0;
  let hpingProc: ChildProcess;

  if (isRoot) {
    // Already running as root, no need for sudo
    console.log("Running as root, spawning hping3 directly...");
    hpingProc = spawn("hping3", ["--udp", "--flood", "-d", "6500", "127.0.0.1", "-p", "9000"], {
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
  } else {
    // Not root, use sudo with password
    const sudoPassword = process.env.SUDO_PASSWORD || "";
    hpingProc = spawn("sudo", ["-S", "hping3", "--udp", "--flood", "-d", "6500", "127.0.0.1", "-p", "9000"], {
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: ["pipe", "pipe", "pipe"],
    });
    
    // Write password to stdin
    if (hpingProc.stdin) {
      hpingProc.stdin.write(sudoPassword + "\n");
      hpingProc.stdin.end();
    }
  }

  simulation.processes.push(hpingProc);

  const handleData = (data: Buffer) => {
    const lines = data.toString().split("\n").filter((l: string) => l.trim());
    for (const line of lines) {
      // Skip password prompts
      if (line.includes("[sudo]") || line.includes("password for")) {
        continue;
      }
      let cleanLine = stripAnsi(line);
      broadcast({
        type: "log",
        role: "eavesdropper",
        message: `[hping3] ${cleanLine}`,
        logType: "attack",
        timestamp: new Date().toISOString(),
      });
    }
  };

  hpingProc.stdout?.on("data", handleData);
  hpingProc.stderr?.on("data", handleData);

  hpingProc.on("close", (code) => {
    broadcast({
      type: "log",
      role: "eavesdropper",
      message: `hping3 attack stopped (exit code: ${code})`,
      logType: "info",
      timestamp: new Date().toISOString(),
    });
  });

  hpingProc.on("error", (err) => {
    broadcast({
      type: "log",
      role: "eavesdropper",
      message: `hping3 error: ${err.message}`,
      logType: "attack",
      timestamp: new Date().toISOString(),
    });
  });
}

// WebSocket connection handler
wss.on("connection", (ws) => {
  console.log("Client connected");

  ws.send(
    JSON.stringify({
      type: "status",
      status: simulation.running ? "running" : "idle",
      phase: simulation.phase,
    })
  );

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString());

      switch (msg.action) {
        case "start_eavesdropper":
          startEavesdropperDemo(msg.mode || "plain");
          break;

        case "start_ddos":
          startDdosDemo(msg.mode || "plain");
          break;

        case "start_hping3":
          startHping3();
          break;

        case "stop":
          killAllProcesses();
          broadcast({
            type: "status",
            status: "stopped",
            message: "Simulation stopped by user.",
          });
          break;

        default:
          ws.send(JSON.stringify({ type: "error", message: `Unknown action: ${msg.action}` }));
      }
    } catch {
      ws.send(JSON.stringify({ type: "error", message: "Invalid message format" }));
    }
  });

  ws.on("close", () => {
    console.log("Client disconnected");
  });
});

// REST endpoints for health check
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", simulation: simulation.phase });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🛰  LEO Security Dashboard Server running on http://0.0.0.0:${PORT}`);
});

// Cleanup on exit
process.on("SIGINT", () => {
  killAllProcesses();
  process.exit(0);
});
process.on("SIGTERM", () => {
  killAllProcesses();
  process.exit(0);
});
