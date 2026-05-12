import path from "path";
import { fileURLToPath } from "url";
import { ProcessManager } from "./processManager.js";
import { stripAnsi, detectLogType, ddosDetectLogType, parseAvgInterval } from "./utils.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DDOS_DIR = path.resolve(__dirname, "../../ddos/LEO");

export async function startDdosDemo(processManager: ProcessManager, mode = "plain") {
  processManager.killAllProcesses();
  processManager.state.running = true;
  processManager.state.phase = `ddos-${mode}`;

  processManager.broadcast({
    type: "status",
    status: "starting",
    phase: processManager.state.phase,
    message: `Starting individual ddos components (${mode})...`,
  });

  const lineTransform = (rawLine: string, currentRole: string) => {
    let cleanLine = stripAnsi(rawLine);
    let role = currentRole;

    if (cleanLine.startsWith("[SENDER]")) {
      role = "sender";
      cleanLine = cleanLine.replace("[SENDER] ", "");
    } else if (cleanLine.startsWith("[RECEIVER]")) {
      role = "receiver";
      cleanLine = cleanLine.replace("[RECEIVER] ", "");
    } else if (cleanLine.startsWith("[SATELLITE]")) {
      role = "system";
    }

    const avgInterval = role === "receiver" ? parseAvgInterval(cleanLine) : null;
    const logType = avgInterval !== null ? ddosDetectLogType(avgInterval) : detectLogType(rawLine);

    return {
      role,
      message: cleanLine,
      logType,
    };
  };

  try {
    processManager.spawnCommand("python3", ["receiver.py", "--local"], DDOS_DIR, "receiver", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "127.0.0.1", "127.0.0.1", "9000", "9001"], DDOS_DIR, "system", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "127.0.0.1", "127.0.0.1", "9001", "9002"], DDOS_DIR, "system", { detached: true, lineTransform });

    await new Promise((resolve) => setTimeout(resolve, 1500));

    const senderProc = processManager.spawnCommand("python3", ["sender.py", mode, "--local"], DDOS_DIR, "sender", { detached: true, lineTransform });
    senderProc.on("close", (code) => {
      processManager.state.running = false;
      processManager.broadcast({
        type: "status",
        status: "stopped",
        message: `Simulation finished (sender exit code: ${code})`,
      });
    });
  } catch (err: any) {
    processManager.state.running = false;
    processManager.broadcast({
      type: "error",
      message: `Failed to start simulation: ${err?.message ?? err}`,
    });
  }
}

export async function startJammingDemo(processManager: ProcessManager, mode = "plain") {
  processManager.killAllProcesses();
  processManager.state.running = true;
  processManager.state.phase = `jamming-${mode}`;

  processManager.broadcast({
    type: "status",
    status: "starting",
    phase: processManager.state.phase,
    message: `Starting individual jamming components (${mode})...`,
  });

  const lineTransform = (rawLine: string, currentRole: string) => {
    let cleanLine = stripAnsi(rawLine);
    let role = currentRole;

    if (cleanLine.startsWith("[SENDER]")) {
      role = "sender";
      cleanLine = cleanLine.replace("[SENDER] ", "");
    } else if (cleanLine.startsWith("[RECEIVER]")) {
      role = "receiver";
      cleanLine = cleanLine.replace("[RECEIVER] ", "");
    } else if (cleanLine.startsWith("[SATELLITE]")) {
      role = "system";
    }

    return {
      role,
      message: cleanLine,
      logType: detectLogType(rawLine),
    };
  };

  try {
    processManager.spawnCommand("python3", ["receiver.py", "--local"], DDOS_DIR, "receiver", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "127.0.0.1", "127.0.0.1", "9000", "9001"], DDOS_DIR, "system", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "127.0.0.1", "127.0.0.1", "9001", "9002"], DDOS_DIR, "system", { detached: true, lineTransform });

    await new Promise((resolve) => setTimeout(resolve, 1500));

    const senderProc = processManager.spawnCommand("python3", ["sender.py", mode, "--local"], DDOS_DIR, "sender", { detached: true, lineTransform });
    senderProc.on("close", (code) => {
      processManager.state.running = false;
      processManager.broadcast({
        type: "status",
        status: "stopped",
        message: `Simulation finished (sender exit code: ${code})`,
      });
    });
  } catch (err: any) {
    processManager.state.running = false;
    processManager.broadcast({
      type: "error",
      message: `Failed to start simulation: ${err?.message ?? err}`,
    });
  }
}

export function runDdosRuleScript(processManager: ProcessManager, scriptFile: string) {
  processManager.broadcast({
    type: "log",
    role: "eavesdropper",
    message: `Executing ${scriptFile}...`,
    logType: "info",
    timestamp: new Date().toISOString(),
  });

  processManager.spawnCommand("sh", [`./${scriptFile}`], DDOS_DIR, "eavesdropper", {
    detached: true,
    prefix: `[${scriptFile}]`,
  });
}

export function startHping3(processManager: ProcessManager) {
  processManager.broadcast({
    type: "log",
    role: "eavesdropper",
    message: "Starting hping3 DDoS attack: --udp --flood -d 6500 127.0.0.1 -p 9000",
    logType: "attack",
    timestamp: new Date().toISOString(),
  });

  processManager.spawnHping3();
}

export function stopHping3(processManager: ProcessManager) {
  processManager.stopHping3();
}
