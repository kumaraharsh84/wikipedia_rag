import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { execSync } from "node:child_process";

const root = process.cwd();
const frontendDir = resolve(root, "frontend_react");
const frontendDist = resolve(frontendDir, "dist");
const rootDist = resolve(root, "dist");

execSync("npm run build --workspace frontend_react", {
  cwd: root,
  stdio: "inherit",
});

if (!existsSync(frontendDist)) {
  throw new Error(`Expected frontend build output at ${frontendDist}`);
}

rmSync(rootDist, { recursive: true, force: true });
mkdirSync(rootDist, { recursive: true });
cpSync(frontendDist, rootDist, { recursive: true });
