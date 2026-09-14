import { build } from 'vite';
import { buildContext } from './build-context.mjs';

if (!buildContext()) throw new Error('Use npm run build to acquire the build lock');
// The runner loads configuration without writing bundled config into node_modules.
await build({ configLoader: 'runner' });
