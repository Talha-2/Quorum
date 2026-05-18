/**
 * Free a TCP port by stopping processes that are listening on it.
 * Usage: node scripts/free-port.mjs 3000
 */
import { execSync } from "node:child_process";

const port = Number(process.argv[2] || 3000);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error(`Invalid port: ${process.argv[2]}`);
  process.exit(1);
}

const isWin = process.platform === "win32";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getPidsWindows(targetPort) {
  const out = execSync("netstat -ano", { encoding: "utf8" });
  const pids = new Set();
  const suffix = `:${targetPort}`;
  for (const line of out.split(/\r?\n/)) {
    if (!line.includes("LISTENING")) continue;
    const trimmed = line.trim();
    if (!trimmed.includes(suffix)) continue;
    const parts = trimmed.split(/\s+/);
    const pid = Number(parts[parts.length - 1]);
    if (pid > 0) pids.add(pid);
  }
  return [...pids];
}

function getPidsUnix(targetPort) {
  try {
    const out = execSync(`lsof -ti tcp:${targetPort} -sTCP:LISTEN`, { encoding: "utf8" });
    return out
      .split(/\r?\n/)
      .map((s) => Number(s.trim()))
      .filter((n) => n > 0);
  } catch {
    return [];
  }
}

function killPid(pid) {
  try {
    if (isWin) {
      execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
    } else {
      process.kill(pid, "SIGTERM");
    }
    console.log(`  Stopped PID ${pid} on port ${port}`);
    return true;
  } catch {
    console.warn(`  Could not stop PID ${pid}`);
    return false;
  }
}

const pids = isWin ? getPidsWindows(port) : getPidsUnix(port);
if (pids.length === 0) {
  console.log(`  Port ${port} is already free.`);
} else {
  for (const pid of pids) killPid(pid);
  await sleep(400);
  console.log(`  Port ${port} cleared.`);
}
