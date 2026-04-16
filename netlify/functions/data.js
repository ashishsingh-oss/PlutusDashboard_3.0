const { getStore } = require("@netlify/blobs");

const RETRIES = 3;
const TIMEOUT_MS = 20000;
const BLOB_STORE = "plutus-dashboard-3";
const BLOB_KEY = "latest-data.csv";
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithTimeout(url, timeoutMs) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      headers: { "User-Agent": "NetlifyFunctionProxy" },
      signal: controller.signal
    });
  } finally {
    clearTimeout(id);
  }
}

async function fetchCsvFromUpstream(upstreamUrl) {
  let lastErr = null;
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    try {
      const url = `${upstreamUrl}${upstreamUrl.includes("?") ? "&" : "?"}_t=${Date.now()}`;
      const resp = await fetchWithTimeout(url, TIMEOUT_MS);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const csv = await resp.text();
      if (!csv || !csv.trim()) throw new Error("Empty CSV response");
      return csv;
    } catch (err) {
      lastErr = err;
      await sleep(300 * attempt);
    }
  }
  throw lastErr || new Error("unknown error");
}

exports.handler = async function handler() {
  const upstreamUrl = (process.env.UPSTREAM_URL || "").trim();
  if (!upstreamUrl || !String(upstreamUrl).trim()) {
    return {
      statusCode: 500,
      headers: { "content-type": "text/plain; charset=utf-8" },
      body: "Configure UPSTREAM_URL (Redash CSV export URL) in Netlify environment variables."
    };
  }

  let store = null;
  try {
    store = getStore(BLOB_STORE);
  } catch (_) {
    store = null;
  }

  if (store) {
    try {
      const cachedCsv = await store.get(BLOB_KEY, { type: "text" });
      if (cachedCsv && cachedCsv.trim()) {
        return {
          statusCode: 200,
          headers: {
            "content-type": "text/csv; charset=UTF-8",
            "access-control-allow-origin": "*",
            "cache-control": "no-store"
          },
          body: cachedCsv
        };
      }
    } catch (_) {
      // Fall through and fetch directly from upstream.
    }
  }

  try {
    const csv = await fetchCsvFromUpstream(upstreamUrl);
    if (store) {
      try {
        await store.set(BLOB_KEY, csv, { metadata: { refreshedAt: new Date().toISOString() } });
      } catch (_) {
        // Non-blocking: return fresh CSV even if cache write fails.
      }
    }

    return {
      statusCode: 200,
      headers: {
        "content-type": "text/csv; charset=UTF-8",
        "access-control-allow-origin": "*",
        "cache-control": "no-store"
      },
      body: csv
    };
  } catch (lastErr) {
    return {
      statusCode: 502,
      headers: { "content-type": "text/plain; charset=utf-8" },
      body: `Upstream fetch failed: ${lastErr ? lastErr.message : "unknown error"}`
    };
  }
};
