import path from "path";
import { fileURLToPath } from "url";
import { ProcessManager } from "./processManager.js";
import { stripAnsi, detectLogType } from "./utils.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const EAVESDROPPER_DIR = path.resolve(__dirname, "../../eavesdropper");

export async function startEavesdropperDemo(processManager: ProcessManager, mode = "plain") {
  processManager.killAllProcesses();
  processManager.state.running = true;
  processManager.state.phase = `eavesdropper-${mode}`;

  processManager.broadcast({
    type: "status",
    status: "starting",
    phase: processManager.state.phase,
    message: `Starting individual eavesdropper components (${mode})...`,
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
    } else if (cleanLine.startsWith("[EAVESDROPPER]")) {
      role = "eavesdropper";
      cleanLine = cleanLine.replace("[EAVESDROPPER] ", "");
    } else if (cleanLine.startsWith("[SAT-A]") || cleanLine.startsWith("[SAT-B]") || cleanLine.startsWith("[SAT-C]")) {
      role = "system";
    }

    return {
      role,
      message: cleanLine,
      logType: detectLogType(rawLine),
    };
  };

  try {
    processManager.spawnCommand("python3", ["receiver.py", "--local", "--dashboard"], EAVESDROPPER_DIR, "receiver", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "sat-c", "--local", "--dashboard"], EAVESDROPPER_DIR, "system", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "sat-b", "--local", "--dashboard"], EAVESDROPPER_DIR, "system", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["eavesdropper.py", "--local", "--dashboard"], EAVESDROPPER_DIR, "eavesdropper", { detached: true, lineTransform });
    processManager.spawnCommand("python3", ["satellite.py", "sat-a", "--local", "--dashboard"], EAVESDROPPER_DIR, "system", { detached: true, lineTransform });

    await new Promise((resolve) => setTimeout(resolve, 1500));

    const senderProc = processManager.spawnCommand("python3", ["sender.py", mode, "--local", "--dashboard"], EAVESDROPPER_DIR, "sender", { detached: true, lineTransform });
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
