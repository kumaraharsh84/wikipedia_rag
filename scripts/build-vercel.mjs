import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const frontendDist = resolve(root, "frontend_react", "dist");
const rootDist = resolve(root, "dist");

if (!existsSync(frontendDist)) {
  throw new Error(`Expected frontend build output at ${frontendDist}`);
}

rmSync(rootDist, { recursive: true, force: true });
mkdirSync(rootDist, { recursive: true });
cpSync(frontendDist, rootDist, { recursive: true });
