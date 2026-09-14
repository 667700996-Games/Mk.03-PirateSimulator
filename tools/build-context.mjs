import { readFileSync, realpathSync, lstatSync } from 'node:fs';
import path from 'node:path';

// The lifecycle supplies fixed owned locations. Never accept arbitrary output paths.
export function buildContext() {
  const job = process.env.PIRATE_BUILD_JOB;
  if (!job) return null;
  const root = process.env.PIRATE_BUILD_ROOT;
  if (!root || !/^\d{16,20}-[a-f0-9]{12}$/.test(path.basename(job)) ||
      path.dirname(job) !== path.join(root, '.build-work', 'jobs') ||
      lstatSync(job).isSymbolicLink() || realpathSync(job) !== job) {
    throw new Error('Invalid owned build workspace');
  }
  const owner = JSON.parse(readFileSync(path.join(job, '.owner.json'), 'utf8'));
  if (owner.schema !== 'piratesimulator-build-v1' || owner.root !== root || owner.kind !== 'job' ||
      realpathSync(process.cwd()) !== path.join(job, 'project')) {
    throw new Error('Build workspace ownership mismatch');
  }
  return { job, output: path.join(job, 'package'), cache: path.join(job, 'vite-cache') };
}
