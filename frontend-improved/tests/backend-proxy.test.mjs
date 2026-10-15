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
let testAccessToken = "verified-test-access-token";
const originalRouteRequire = routeModule.require.bind(routeModule);
routeModule.require = (id) => {
  if (id === "@/lib/supabase/server") {
    return { getAuthenticatedAccessToken: async () => testAccessToken };
  }
  return originalRouteRequire(id);
};
routeModule._compile(compiled, routePath);

const params = (...segments) => ({
  params: Promise.resolve({ path: segments }),
});

async function withProxyFetch(mockFetch, callback) {
  const originalFetch = globalThis.fetch;
  const originalBackendUrl = process.env.BACKEND_URL;
  const originalAccessToken = testAccessToken;
  globalThis.fetch = mockFetch;
  process.env.BACKEND_URL = "http://backend.test:8000";
  try {
    await callback();
  } finally {
    globalThis.fetch = originalFetch;
    testAccessToken = originalAccessToken;
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
    assert.equal(init.headers.get("authorization"), "Bearer verified-test-access-token");
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
          origin: "http://frontend.test",
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
      { method: "POST", headers: { origin: "http://frontend.test" } },
    );
    const response = await routeModule.exports.POST(
      request,
      params("api", "v1", "demo", "seed"),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { status: "success" });
  });
});

test("POST proxy rejects a cross-origin request before forwarding", async () => {
  await withProxyFetch(async () => {
    assert.fail("cross-origin request must not reach the backend");
  }, async () => {
    const request = new Request("http://frontend.test/api/backend/api/v1/profiles", {
      method: "POST",
      headers: { origin: "https://attacker.example" },
      body: "{}",
    });
    const response = await routeModule.exports.POST(
      request,
      params("api", "v1", "profiles"),
    );
    assert.equal(response.status, 403);
  });
});

test("API proxy does not forward requests without an authenticated session", async () => {
  testAccessToken = null;
  try {
    await withProxyFetch(async () => {
      assert.fail("anonymous request must not reach the backend");
    }, async () => {
      const request = new Request("http://frontend.test/api/backend/api/v1/profiles");
      const response = await routeModule.exports.GET(
        request,
        params("api", "v1", "profiles"),
      );
      assert.equal(response.status, 401);
    });
  } finally {
    testAccessToken = "verified-test-access-token";
  }
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
