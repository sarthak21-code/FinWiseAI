import assert from "node:assert/strict";
import { Module } from "node:module";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const proxyPath = path.resolve(testDirectory, "../src/proxy.ts");
const source = (await import("node:fs")).readFileSync(proxyPath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText;
const proxyModule = new Module(proxyPath);
proxyModule.filename = proxyPath;
proxyModule.paths = Module._nodeModulePaths(path.dirname(proxyPath));
let testClaims = null;
proxyModule.require = (id) => {
  if (id === "@supabase/ssr") {
    return {
      createServerClient: () => ({
        auth: { getClaims: async () => ({ data: { claims: testClaims }, error: null }) },
      }),
    };
  }
  return Module.prototype.require.call(proxyModule, id);
};
proxyModule._compile(compiled, proxyPath);
const callbackPath = path.resolve(testDirectory, "../src/app/auth/callback/route.ts");
const callbackSource = (await import("node:fs")).readFileSync(callbackPath, "utf8");
const callbackCompiled = ts.transpileModule(callbackSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText;
const callbackModule = new Module(callbackPath);
callbackModule.filename = callbackPath;
callbackModule.paths = Module._nodeModulePaths(path.dirname(callbackPath));
let mockExchangeError = null;
let mockVerifyError = null;
callbackModule.require = (id) => {
  if (id === "@/lib/supabase/server") {
    return {
      createSupabaseServerClient: async () => ({
        auth: {
          exchangeCodeForSession: async () => ({ error: mockExchangeError }),
          verifyOtp: async () => ({ error: mockVerifyError }),
        },
      }),
    };
  }
  return Module.prototype.require.call(callbackModule, id);
};
callbackModule._compile(callbackCompiled, callbackPath);
process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "test-publishable-key";

test("unauthenticated page requests redirect to login with requested path", async () => {
  testClaims = null;
  const request = new Request("https://finwise.example/portfolio?tab=holdings");
  request.nextUrl = new URL(request.url);
  request.cookies = { getAll: () => [], set: () => undefined };
  const response = await proxyModule.exports.proxy(request);
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"),
    "https://finwise.example/login?next=%2Fportfolio%3Ftab%3Dholdings");
});

test("unauthenticated API requests receive a non-cacheable 401", async () => {
  testClaims = null;
  const request = new Request("https://finwise.example/api/backend/api/v1/profiles");
  request.nextUrl = new URL(request.url);
  request.cookies = { getAll: () => [], set: () => undefined };
  const response = await proxyModule.exports.proxy(request);
  assert.equal(response.status, 401);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("authenticated requests continue and login remains public", async () => {
  testClaims = { sub: "verified-user" };
  const protectedRequest = new Request("https://finwise.example/evaluation");
  protectedRequest.nextUrl = new URL(protectedRequest.url);
  protectedRequest.cookies = { getAll: () => [], set: () => undefined };
  const protectedResponse = await proxyModule.exports.proxy(protectedRequest);
  assert.equal(protectedResponse.headers.get("x-middleware-next"), "1");

  testClaims = null;
  const loginRequest = new Request("https://finwise.example/login");
  loginRequest.nextUrl = new URL(loginRequest.url);
  loginRequest.cookies = { getAll: () => [], set: () => undefined };
  const loginResponse = await proxyModule.exports.proxy(loginRequest);
  assert.equal(loginResponse.headers.get("x-middleware-next"), "1");
});

test("auth callback rejects external redirect targets", async () => {
  mockExchangeError = null;
  const request = new Request(
    "https://finwise.example/auth/callback?code=local-test-code&next=%2F%2Fevil.example%2Fsteal",
  );
  request.nextUrl = new URL(request.url);
  const response = await callbackModule.exports.GET(request);
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "https://finwise.example/");
});

test("auth callback redirects to otp-expired when Supabase returns otp_expired error", async () => {
  const request = new Request(
    "https://finwise.example/auth/callback?error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired",
  );
  request.nextUrl = new URL(request.url);
  const response = await callbackModule.exports.GET(request);
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "https://finwise.example/login?error=otp-expired");
});

test("auth callback redirects to otp-expired when code exchange fails with expired error", async () => {
  mockExchangeError = { code: "otp_expired", message: "Email link is invalid or has expired", status: 400 };
  try {
    const request = new Request("https://finwise.example/auth/callback?code=expired-code");
    request.nextUrl = new URL(request.url);
    const response = await callbackModule.exports.GET(request);
    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "https://finwise.example/login?error=otp-expired");
  } finally {
    mockExchangeError = null;
  }
});

test("auth callback redirects to sign-in error when code exchange fails with generic error", async () => {
  mockExchangeError = { code: "unexpected", message: "Internal server error", status: 500 };
  try {
    const request = new Request("https://finwise.example/auth/callback?code=bad-code");
    request.nextUrl = new URL(request.url);
    const response = await callbackModule.exports.GET(request);
    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "https://finwise.example/login?error=sign-in");
  } finally {
    mockExchangeError = null;
  }
});

test("auth callback successfully verifies token_hash and redirects to safe next target", async () => {
  mockVerifyError = null;
  const request = new Request(
    "https://finwise.example/auth/callback?token_hash=valid-hash&type=email&next=%2Fportfolio",
  );
  request.nextUrl = new URL(request.url);
  const response = await callbackModule.exports.GET(request);
  assert.equal(response.status, 307);
  assert.equal(response.headers.get("location"), "https://finwise.example/portfolio");
});
