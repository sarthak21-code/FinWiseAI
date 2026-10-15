import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Module } from "node:module";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const routePath = path.resolve(
  testDirectory,
  "../src/app/api/backend/[...path]/route.ts",
);
const source = readFileSync(routePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const routeModule = new Module(routePath);
routeModule.filename = routePath;
routeModule.paths = Module._nodeModulePaths(path.dirname(routePath));
routeModule._compile(compiled, routePath);

const params = (...segments) => ({
  params: Promise.resolve({ path: segments }),
});

async function withProxyFetch(mockFetch, callback) {
  const originalFetch = globalThis.fetch;
  const originalBackendUrl = process.env.BACKEND_URL;
  globalThis.fetch = mockFetch;
  process.env.BACKEND_URL = "http://backend.test:8000";
  try {
    await callback();
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBackendUrl === undefined) {
      delete process.env.BACKEND_URL;
    } else {
      process.env.BACKEND_URL = originalBackendUrl;
    }
  }
}

test("POST profile comparison forwards URL, JSON body, and safe headers", async () => {
  await withProxyFetch(async (url, init) => {
    assert.equal(
      url.href,
      "http://backend.test:8000/api/v1/intelligence/compare-profiles",
    );
    assert.equal(init.method, "POST");
    assert.equal(init.headers.get("content-type"), "application/json");
    assert.equal(init.headers.get("authorization"), null);
    assert.equal(init.headers.get("cookie"), null);
    assert.deepEqual(
      JSON.parse(Buffer.from(init.body).toString("utf8")),
      {
        symbol: "NVDA",
        profile_a_id: "conservative",
        profile_b_id: "growth",
      },
    );
    return new Response(JSON.stringify({ market_facts_unaltered: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }, async () => {
    const request = new Request(
      "http://frontend.test/api/backend/api/v1/intelligence/compare-profiles",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "must-not-forward",
          cookie: "must-not-forward",
        },
        body: JSON.stringify({
          symbol: "NVDA",
          profile_a_id: "conservative",
          profile_b_id: "growth",
        }),
      },
    );
    const response = await routeModule.exports.POST(
      request,
      params("api", "v1", "intelligence", "compare-profiles"),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { market_facts_unaltered: true });
  });
});

test("POST demo seed reaches its backend endpoint without inventing a body", async () => {
  await withProxyFetch(async (url, init) => {
    assert.equal(url.href, "http://backend.test:8000/api/v1/demo/seed");
    assert.equal(init.method, "POST");
    assert.equal(init.body, undefined);
    return new Response(JSON.stringify({ status: "success" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }, async () => {
    const request = new Request(
      "http://frontend.test/api/backend/api/v1/demo/seed",
      { method: "POST" },
    );
    const response = await routeModule.exports.POST(
      request,
      params("api", "v1", "demo", "seed"),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: "success" });
  });
});

test("GET proxy preserves query parameters and upstream response status/body", async () => {
  await withProxyFetch(async (url, init) => {
    assert.equal(
      url.href,
      "http://backend.test:8000/api/v1/documents/search?q=cloud+revenue&symbol=MSFT",
    );
    assert.equal(init.method, "GET");
    return new Response(JSON.stringify({ detail: "not found" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
  }, async () => {
    const request = new Request(
      "http://frontend.test/api/backend/api/v1/documents/search?q=cloud+revenue&symbol=MSFT",
    );
    const response = await routeModule.exports.GET(
      request,
      params("api", "v1", "documents", "search"),
    );
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { detail: "not found" });
  });
});
