/**
 * server/index.ts — Backend for LEO Security Dashboard
 * Spawns Python simulation processes and streams stdout/stderr
 * to connected WebSocket clients in real-time.
 */

import express from "express";
import http from "http";
import { WebSocketServer, WebSocket } from "ws";
import cors from "cors";
import { fileURLToPath } from "url";
import path from "path";
import "dotenv/config";

import { ProcessManager } from "./processManager.js";
import { startEavesdropperDemo } from "./eavesdropperController.js";
import { startDdosDemo, startJammingDemo, startHping3, stopHping3, runDdosRuleScript } from "./attackController.js";
import { startMitmDemo } from "./mitmController.js";
import type { SimulationState } from "./types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PORT = 3001;

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

const simulation: SimulationState = {
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

const processManager = new ProcessManager(simulation, broadcast);

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
          startEavesdropperDemo(processManager, msg.mode || "plain");
          break;
        case "start_ddos":
          startDdosDemo(processManager, msg.mode || "plain");
          break;
        case "start_hping3":
          startHping3(processManager);
          break;
        case "stop_hping3":
          stopHping3(processManager);
          break;
        case "create_ddos_rules":
          runDdosRuleScript(processManager, "ddos_rule");
          break;
        case "remove_ddos_rules":
          runDdosRuleScript(processManager, "remove_rules");
          break;
        case "stop":
          processManager.killAllProcesses();
          broadcast({
            type: "status",
            status: "stopped",
            message: "Simulation stopped by user.",
          });
          break;
        case "start_jamming":
          startJammingDemo(processManager, msg.mode || "plain");
          break;
        case "start_mitm":
          startMitmDemo(processManager, msg.mode || "plain");
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

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", simulation: simulation.phase });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🛰  LEO Security Dashboard Server running on http://0.0.0.0:${PORT}`);
});

process.on("SIGINT", () => {
  processManager.killAllProcesses();
  process.exit(0);
});

process.on("SIGTERM", () => {
  processManager.killAllProcesses();
  process.exit(0);
});
