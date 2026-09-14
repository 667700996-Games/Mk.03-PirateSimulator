import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';
import { buildContext } from './tools/build-context.mjs';

const context = buildContext();

export default defineConfig({
  plugins: [{
    name: 'owned-build-workspace',
    configResolved(config) {
      if (config.command === 'build' && !context) {
        throw new Error('Use npm run build; builds require an owned workspace and lock');
      }
    }
  }, sveltekit()],
  ...(context ? { cacheDir: context.cache } : {}),
  // Phaser is isolated behind the lazily loaded settlement/sea screens. Its
  // minified engine chunk is ~1.2 MB (~319 KB gzip), so keep the warning gate
  // above that deliberate vendor boundary while watching first-load chunks.
  build: { chunkSizeWarningLimit: 1250 },
  test: {
    include: ['src/**/*.test.ts'],
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    // The 500-resident contract measures per-tick wall time. Running other
    // files in parallel can preempt its worker and turn scheduler delay into a
    // false simulation regression, so keep the quality gate process-isolated.
    fileParallelism: false,
    coverage: {
      reporter: ['text', 'html'],
      include: [
        'src/lib/domain/**/*.ts',
        'src/lib/persistence/**/*.ts',
        'src/lib/settlement/**/*.ts'
      ],
      exclude: ['src/**/*.test.ts', 'src/lib/settlement/catalog.ts'],
      thresholds: {
        statements: 72,
        branches: 58,
        functions: 78,
        lines: 77
      }
    }
  }
});
