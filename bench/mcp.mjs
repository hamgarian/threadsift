// Minimal MCP stdio client: node mcp.mjs '<command json array>' [calls.json]
// Without calls.json it prints the server's tools; with it, runs each {name, arguments} and prints JSON results.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";

const cmd = JSON.parse(process.argv[2]);
const calls = process.argv[3] ? JSON.parse(readFileSync(process.argv[3], "utf8")) : null;
const child = spawn(cmd[0], cmd.slice(1), { stdio: ["pipe", "pipe", "pipe"], shell: process.platform === "win32" });
let buf = "", id = 0;
const pending = new Map();
child.stdout.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line) continue;
    try { const m = JSON.parse(line); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } } catch {}
  }
});
child.stderr.on("data", () => {});
const rpc = (method, params, ms = 120000) => new Promise((res) => {
  const myId = ++id;
  const t = setTimeout(() => { pending.delete(myId); res({ error: { message: `timeout ${ms}ms` } }); }, ms);
  pending.set(myId, (m) => { clearTimeout(t); res(m); });
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: myId, method, params }) + "\n");
});

const init = await rpc("initialize", { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "bench", version: "0" } }, 180000);
if (init.error) { console.log(JSON.stringify({ fatal: init.error })); process.exit(1); }
child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
if (!calls) {
  const t = await rpc("tools/list", {});
  for (const tool of t.result?.tools ?? []) console.log(`${tool.name}: ${(tool.description || "").slice(0, 110).replace(/\s+/g, " ")}\n   args: ${Object.keys(tool.inputSchema?.properties || {}).join(", ")}`);
} else {
  const out = [];
  for (const c of calls) {
    const t0 = Date.now();
    const r = await rpc("tools/call", { name: c.name, arguments: c.arguments });
    const text = (r.result?.content || []).map((x) => x.text || "").join("\n");
    out.push({ task: c.task, tool: c.name, ms: Date.now() - t0, error: r.error?.message || (r.result?.isError ? text.slice(0, 300) : null), text });
  }
  console.log(JSON.stringify(out));
}
child.kill();
process.exit(0);
