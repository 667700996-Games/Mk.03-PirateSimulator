import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat, realpath } from 'node:fs/promises';
import path from 'node:path';

// Serve the validated static package; SvelteKit's deleted SSR intermediate is unnecessary.
const [root, host, port] = process.argv.slice(2);
const types = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
  '.webmanifest': 'application/manifest+json', '.png': 'image/png',
  '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ogg': 'audio/ogg',
  '.woff2': 'font/woff2', '.ico': 'image/x-icon', '.txt': 'text/plain'
};
const server = createServer(async (request, response) => {
  try {
    if (!['GET', 'HEAD'].includes(request.method ?? '')) {
      response.writeHead(405).end();
      return;
    }
    const pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname);
    let file = path.resolve(root, '.' + pathname);
    if (!file.startsWith(root + path.sep) && file !== root) {
      response.writeHead(403).end();
      return;
    }
    try {
      const info = await stat(file);
      if (info.isDirectory()) file = path.join(file, 'index.html');
      await stat(file);
    } catch {
      if (request.headers.accept?.includes('text/html')) file = path.join(root, 'index.html');
      else { response.writeHead(404).end(); return; }
    }
    file = await realpath(file);
    if (!file.startsWith(root + path.sep)) { response.writeHead(403).end(); return; }
    const info = await stat(file);
    response.writeHead(200, {
      'Content-Type': types[path.extname(file)] ?? 'application/octet-stream',
      'Content-Length': info.size, 'Cache-Control': 'no-cache'
    });
    if (request.method === 'HEAD') response.end();
    else createReadStream(file).on('error', () => response.destroy()).pipe(response);
  } catch {
    response.writeHead(400).end();
  }
});
server.listen(Number(port), host, () => console.log(`Preview: http://${host}:${port}`));
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(sig, () => { server.close(); server.closeAllConnections(); });
}
