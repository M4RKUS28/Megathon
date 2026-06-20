import { createReadStream, promises as fs } from "node:fs";
import { createServer } from "node:http";
import { extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("./dist/", import.meta.url)));
const port = Number(process.env.PORT || 4173);

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".gif": "image/gif",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2"
};

function resolveRequestPath(pathname) {
  const decoded = decodeURIComponent(pathname);
  const relativePath = decoded.replace(/^\/+/, "");
  const filePath = resolve(root, relativePath);
  return filePath === root || filePath.startsWith(`${root}/`) ? filePath : null;
}

async function existingFile(filePath) {
  try {
    const stat = await fs.stat(filePath);
    return stat.isFile() ? filePath : null;
  } catch {
    return null;
  }
}

async function getFilePath(pathname) {
  const requestedPath = resolveRequestPath(pathname);
  if (!requestedPath) return null;

  const stat = await fs.stat(requestedPath).catch(() => null);
  if (stat?.isDirectory()) return existingFile(resolve(requestedPath, "index.html"));
  if (stat?.isFile()) return requestedPath;

  if (extname(pathname)) return null;
  return existingFile(resolve(root, "index.html"));
}

const server = createServer(async (request, response) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, { Allow: "GET, HEAD" });
    response.end();
    return;
  }

  const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
  const filePath = await getFilePath(url.pathname);

  if (!filePath) {
    response.writeHead(404);
    response.end();
    return;
  }

  const extension = extname(filePath);
  const headers = {
    "Content-Type": mimeTypes[extension] || "application/octet-stream",
    "Cache-Control": filePath.endsWith("index.html") ? "no-cache" : "public, max-age=31536000, immutable"
  };

  response.writeHead(200, headers);

  if (request.method === "HEAD") {
    response.end();
    return;
  }

  const stream = createReadStream(filePath);
  stream.on("error", () => response.destroy());
  stream.pipe(response);
});

server.listen(port, "0.0.0.0");
