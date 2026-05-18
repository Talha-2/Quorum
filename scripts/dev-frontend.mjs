/**
 * Start Next.js dev server on the first bindable localhost port.
 * Handles Windows Hyper-V/WSL "excluded port" ranges where 3000 is reserved
 * but netstat shows nothing listening (EACCES on bind).
 */
import { spawn } from "node:child_process";
import { execSync } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const frontendDir = path.join(repoRoot, "frontend");
const host = process.env.FRONTEND_HOST || "127.0.0.1";
const preferred = Number(process.env.FRONTEND_PORT || process.env.PORT || 3000);

const isWin = process.platform === "win32";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getWindowsExcludedRanges() {
  if (!isWin) return [];
  try {
    const out = execSync("netsh interface ipv4 show excludedportrange protocol=tcp", {
      encoding: "utf8",
    });
    const ranges = [];
    for (const line of out.split(/\r?\n/)) {
      const m = line.match(/^\s*(\d+)\s+(\d+)\s/);
      if (m) ranges.push([Number(m[1]), Number(m[2])]);
    }
    return ranges;
  } catch {
    return [];
  }
}

function isPortExcluded(port, ranges) {
  return ranges.some(([start, end]) => port >= start && port <= end);
}

function getPidsOnPort(targetPort) {
  if (!isWin) {
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
  const out = execSync("netstat -ano", { encoding: "utf8" });
  const pids = new Set();
  const needle = `:${targetPort}`;
  for (const line of out.split(/\r?\n/)) {
    if (!line.includes("LISTENING") || !line.includes(needle)) continue;
    const parts = line.trim().split(/\s+/);
    const pid = Number(parts[parts.length - 1]);
    if (pid > 0) pids.add(pid);
  }
  return [...pids];
}

function killPids(pids, targetPort) {
  for (const pid of pids) {
    try {
      if (isWin) {
        execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
      } else {
        process.kill(pid, "SIGTERM");
      }
      console.log(`  Stopped PID ${pid} on port ${targetPort}`);
    } catch {
      console.warn(`  Could not stop PID ${pid}`);
    }
  }
}

function canBind(bindHost, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", (err) => {
      server.close?.();
      resolve({ ok: false, err });
    });
    server.once("listening", () => {
      server.close(() => resolve({ ok: true }));
    });
    server.listen(port, bindHost);
  });
}

function nextOutsideExcluded(port, ranges) {
  let p = port;
  while (p <= 65535) {
    const hit = ranges.find(([start, end]) => p >= start && p <= end);
    if (!hit) return p;
    p = hit[1] + 1;
  }
  return null;
}

function buildCandidates(excludedRanges) {
  const candidates = [];
  const add = (p) => {
    if (p == null || p < 1024 || p > 65535 || candidates.includes(p)) return;
    if (isPortExcluded(p, excludedRanges)) return;
    candidates.push(p);
  };

  add(preferred);
  add(nextOutsideExcluded(preferred, excludedRanges));

  // Common dev ports that usually sit outside Hyper-V/WSL reservation blocks
  for (const p of [3117, 3200, 4000, 8080]) add(p);
  if (isWin) add(3010);

  for (let p = preferred + 1; p <= preferred + 15; p++) add(p);
  if (preferred !== 3000) add(3000);

  return candidates;
}

function scanBindablePorts(excludedRanges, maxTries = 80) {
  const found = [];
  let port = nextOutsideExcluded(Math.max(preferred, 1024), excludedRanges);
  while (port != null && found.length < maxTries) {
    if (!found.includes(port)) found.push(port);
    port = nextOutsideExcluded(port + 1, excludedRanges);
  }
  return found;
}

async function pickPort(excludedRanges) {
  const candidates = [
    ...buildCandidates(excludedRanges),
    ...scanBindablePorts(excludedRanges),
  ];

  for (const port of candidates) {
    if (isPortExcluded(port, excludedRanges)) {
      console.log(`  Port ${port} is in a Windows excluded range (skipped)`);
      continue;
    }

    const pids = getPidsOnPort(port);
    if (pids.length > 0) {
      console.log(`  Clearing port ${port}...`);
      killPids(pids, port);
      await sleep(400);
    }

    const result = await canBind(host, port);
    if (result.ok) return port;

    const code = result.err?.code;
    if (code === "EACCES") {
      console.log(`  Port ${port} blocked (EACCES — likely reserved by Windows)`);
    } else if (code === "EADDRINUSE") {
      console.log(`  Port ${port} still in use`);
    } else {
      console.log(`  Port ${port} unavailable (${code || result.err?.message})`);
    }
  }

  return null;
}

const excludedRanges = getWindowsExcludedRanges();
if (excludedRanges.length > 0 && isPortExcluded(preferred, excludedRanges)) {
  console.log(
    `Note: port ${preferred} is inside a Windows excluded range (common with Hyper-V/WSL).`,
  );
  console.log("  Run: netsh interface ipv4 show excludedportrange protocol=tcp");
}

console.log(`Finding a bindable port for Next.js on ${host}...`);
const port = await pickPort(excludedRanges);

if (!port) {
  console.error(
    "Could not find a bindable port. Try: set FRONTEND_PORT=3117 (PowerShell) or FRONTEND_PORT=3117 npm run dev",
  );
  process.exit(1);
}

if (port !== preferred) {
  console.log(`Using port ${port} instead of ${preferred}.`);
} else {
  console.log(`Using port ${port}.`);
}

console.log(`\n  → http://${host}:${port}\n`);

const child = spawn("npx", ["next", "dev", "-H", host, "-p", String(port)], {
  cwd: frontendDir,
  stdio: "inherit",
  shell: true,
  env: { ...process.env, PORT: String(port) },
});

child.on("exit", (code) => process.exit(code ?? 0));
