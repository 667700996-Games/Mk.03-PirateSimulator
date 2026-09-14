import adapter from '@sveltejs/adapter-static';
import { buildContext } from './tools/build-context.mjs';

const context = buildContext();
const staticAdapter = adapter({
  fallback: 'index.html',
  ...(context ? { pages: context.output, assets: context.output } : {})
});

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: {
      ...staticAdapter,
      async adapt(builder) {
        if (!context) throw new Error('Use npm run build; unmanaged builds cannot replace build/');
        await staticAdapter.adapt(builder);
      }
    }
  }
};

export default config;
