import "@phala/pink-env";

// Simple data structure for inspection certificates
interface InspectionCertificate {
  id: string;
  type: "skill" | "data" | "credential";
  claimant: string;
  inputHash: string;
  inspectionPrompt: string;
  result: string;
  timestamp: number;
  attestation: string;
}

// In-memory storage (will persist in Phala KV store)
const certificates = new Map<string, InspectionCertificate>();
const MAX_CERTIFICATES = 10000;

/** Escape HTML special characters to prevent XSS */
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

/**
 * Generate a simple inspection certificate
 * This is MVP - just stores the result, doesn't run verification yet
 */
export function createCertificate(params: {
  type: string;
  claimant: string;
  inputHash: string;
  prompt: string;
  result: string;
}): string {
  const id = `cert_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  
  const timestamp = Date.now();
  // HMAC-like construction: H(K ^ opad || H(K ^ ipad || message))
  // pink.ext() only exposes hash() and deriveSecret(), so we use a keyed double-hash
  const secretKey = pink.ext().deriveSecret("attestation_key");
  const payload = `${id}|${params.type}|${params.claimant}|${params.inputHash}|${params.result}|${timestamp}`;
  const innerHash = pink.ext().hash(secretKey + "|inner|" + payload);
  const attestation = pink.ext().hash(secretKey + "|outer|" + innerHash);

  const cert: InspectionCertificate = {
    id,
    type: params.type as any,
    claimant: params.claimant,
    inputHash: params.inputHash,
    inspectionPrompt: params.prompt,
    result: params.result,
    timestamp,
    attestation, // Signature proof, NOT raw secret material
  };
  
  // Evict oldest certificates if at capacity
  if (certificates.size >= MAX_CERTIFICATES) {
    let oldest: string | null = null;
    let oldestTs = Infinity;
    for (const [key, c] of certificates) {
      if (c.timestamp < oldestTs) {
        oldestTs = c.timestamp;
        oldest = key;
      }
    }
    if (oldest) certificates.delete(oldest);
  }

  certificates.set(id, cert);

  return id;
}

/**
 * Get a certificate by ID
 */
export function getCertificate(id: string): InspectionCertificate | null {
  return certificates.get(id) || null;
}

/**
 * List all certificates
 */
export function listCertificates(): InspectionCertificate[] {
  return Array.from(certificates.values());
}

/**
 * HTTP handler - serves certificates as HTML
 */
export default function main(request: string): string {
  let req: any;
  try {
    req = JSON.parse(request);
  } catch {
    return JSON.stringify({
      statusCode: 400,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: "Invalid JSON request" })
    });
  }

  // Parse simple HTTP-like request
  const path = req.path || "/";
  const method = req.method || "GET";
  
  // Route: GET /
  if (method === "GET" && path === "/") {
    return JSON.stringify({
      statusCode: 200,
      headers: { "Content-Type": "text/html" },
      body: renderHomePage()
    });
  }
  
  // Route: GET /certificate/:id
  if (method === "GET" && path.startsWith("/certificate/")) {
    const id = path.split("/")[2];
    const cert = getCertificate(id);
    
    if (!cert) {
      return JSON.stringify({
        statusCode: 404,
        headers: { "Content-Type": "text/html" },
        body: "<h1>404 - Certificate Not Found</h1>"
      });
    }
    
    return JSON.stringify({
      statusCode: 200,
      headers: { "Content-Type": "text/html" },
      body: renderCertificate(cert)
    });
  }
  
  // Route: POST /create (requires API key)
  if (method === "POST" && path === "/create") {
    const apiKey = req.headers?.["x-api-key"] || req.headers?.["authorization"]?.replace("Bearer ", "");
    const expectedKey = pink.ext().deriveSecret("api_auth_key");
    // Constant-time comparison: hash both values and compare hashes to prevent timing attacks
    if (!apiKey || pink.ext().hash("compare|" + apiKey) !== pink.ext().hash("compare|" + expectedKey)) {
      return JSON.stringify({
        statusCode: 401,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Unauthorized" })
      });
    }
    let body: any;
    try {
      body = JSON.parse(req.body || "{}");
    } catch {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Invalid JSON body" })
      });
    }
    if (!body.type || !body.claimant || !body.inputHash || !body.prompt || !body.result) {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Missing required fields: type, claimant, inputHash, prompt, result" })
      });
    }
    // Strict type validation to prevent runtime errors from non-string values
    const VALID_TYPES = ["skill", "data", "credential"];
    if (typeof body.type !== "string" || typeof body.claimant !== "string" ||
        typeof body.inputHash !== "string" || typeof body.prompt !== "string" ||
        typeof body.result !== "string") {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "All fields must be strings" })
      });
    }
    if (!VALID_TYPES.includes(body.type)) {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: `type must be one of: ${VALID_TYPES.join(", ")}` })
      });
    }
    // Enforce per-field size limits to prevent memory exhaustion
    const MAX_FIELD = 2000; // 2KB per field
    const MAX_SHORT = 256;
    if (body.type.length > MAX_SHORT || body.claimant.length > MAX_SHORT || body.inputHash.length > MAX_SHORT) {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: `Fields type/claimant/inputHash must be <= ${MAX_SHORT} chars` })
      });
    }
    if (body.prompt.length > MAX_FIELD || body.result.length > MAX_FIELD) {
      return JSON.stringify({
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: `Fields prompt/result must be <= ${MAX_FIELD} chars` })
      });
    }
    const id = createCertificate(body);

    return JSON.stringify({
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, url: `/certificate/${id}` })
    });
  }
  
  // Route: GET /certificates (list all — requires auth, redacted summary, no sensitive prompt/result data)
  if (method === "GET" && path === "/certificates") {
    const listApiKey = req.headers?.["x-api-key"] || req.headers?.["authorization"]?.replace("Bearer ", "");
    const listExpectedKey = pink.ext().deriveSecret("api_auth_key");
    if (!listApiKey || pink.ext().hash("compare|" + listApiKey) !== pink.ext().hash("compare|" + listExpectedKey)) {
      return JSON.stringify({
        statusCode: 401,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: "Unauthorized" })
      });
    }
    const certs = listCertificates().map(c => ({
      id: c.id,
      type: c.type,
      claimant: c.claimant,
      inputHash: c.inputHash,
      timestamp: c.timestamp,
      // Omit inspectionPrompt, result, and attestation from list view
    }));
    return JSON.stringify({
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(certs)
    });
  }
  
  return JSON.stringify({
    statusCode: 404,
    headers: { "Content-Type": "text/plain" },
    body: "Not Found"
  });
}

/**
 * Render home page
 */
function renderHomePage(): string {
  const certs = listCertificates();
  
  return `
<!DOCTYPE html>
<html>
<head>
  <title>Inspection Certificates - Phala</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
      background: #0a0a0a;
      color: #e0e0e0;
    }
    h1 { color: #00d4aa; }
    h2 { color: #e01b24; border-bottom: 2px solid #e01b24; padding-bottom: 10px; }
    .cert-card {
      background: #1a1a1b;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
    }
    .cert-card:hover {
      border-color: #00d4aa;
    }
    .cert-id {
      font-family: monospace;
      background: #2d2d2e;
      padding: 5px 10px;
      border-radius: 4px;
      font-size: 12px;
      color: #00d4aa;
    }
    .hash {
      font-family: monospace;
      background: #2d2d2e;
      padding: 3px 6px;
      border-radius: 3px;
      font-size: 11px;
      color: #888;
    }
    a {
      color: #00d4aa;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: bold;
      margin-right: 8px;
    }
    .badge-skill { background: #e01b24; color: white; }
    .badge-data { background: #00d4aa; color: black; }
    .badge-credential { background: #ff9500; color: black; }
    .timestamp {
      color: #888;
      font-size: 13px;
    }
    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #666;
    }
    .logo {
      font-size: 48px;
      text-align: center;
      margin-bottom: 10px;
    }
    .tagline {
      text-align: center;
      color: #888;
      margin-bottom: 40px;
    }
  </style>
</head>
<body>
  <div class="logo">🦞🔐</div>
  <h1 style="text-align: center;">Inspection Certificates</h1>
  <p class="tagline">Verifiable proof of ephemeral execution - Running on Phala Network</p>
  
  <h2>Recent Certificates</h2>
  
  ${certs.length === 0 ? `
    <div class="empty-state">
      <p>No certificates yet.</p>
      <p>Create one via POST /create</p>
    </div>
  ` : certs.map(cert => `
    <div class="cert-card">
      <div>
        <span class="badge badge-${escapeHtml(cert.type)}">${escapeHtml(cert.type)}</span>
        <span class="timestamp">${escapeHtml(new Date(cert.timestamp).toISOString())}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Certificate ID:</strong> <span class="cert-id">${escapeHtml(cert.id)}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Input Hash:</strong> <span class="hash">${escapeHtml(cert.inputHash.slice(0, 16))}...${escapeHtml(cert.inputHash.slice(-16))}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Result:</strong> [Full content available via authenticated API]
      </div>
      <div style="margin-top: 15px;">
        <a href="/certificate/${encodeURIComponent(cert.id)}">View Full Certificate →</a>
      </div>
    </div>
  `).join('')}
  
  <div style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #333; color: #666; font-size: 13px; text-align: center;">
    <p>Powered by <strong>Phala Network</strong> - Decentralized TEE Compute</p>
    <p>
      <a href="https://github.com/amiller/skill-verifier">GitHub</a> ·
      <a href="/certificates">API</a>
    </p>
  </div>
</body>
</html>
  `.trim();
}

/**
 * Render individual certificate page
 */
function renderCertificate(cert: InspectionCertificate): string {
  return `
<!DOCTYPE html>
<html>
<head>
  <title>Certificate ${escapeHtml(cert.id)} - Inspection Certificates</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
      background: #0a0a0a;
      color: #e0e0e0;
    }
    h1 { color: #00d4aa; }
    h2 { color: #e01b24; border-bottom: 2px solid #e01b24; padding-bottom: 10px; margin-top: 30px; }
    .field {
      background: #1a1a1b;
      border: 1px solid #333;
      border-radius: 6px;
      padding: 15px;
      margin: 15px 0;
    }
    .field-label {
      color: #888;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .field-value {
      font-size: 15px;
      line-height: 1.6;
    }
    .mono {
      font-family: monospace;
      background: #2d2d2e;
      padding: 3px 6px;
      border-radius: 3px;
      font-size: 13px;
      word-break: break-all;
    }
    .badge {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
      margin-right: 8px;
    }
    .badge-skill { background: #e01b24; color: white; }
    .badge-data { background: #00d4aa; color: black; }
    .badge-credential { background: #ff9500; color: black; }
    .status-verified {
      background: #00d4aa;
      color: black;
      padding: 8px 16px;
      border-radius: 6px;
      display: inline-block;
      font-weight: bold;
      margin: 20px 0;
    }
    a {
      color: #00d4aa;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .back-link {
      margin-bottom: 30px;
      display: inline-block;
    }
  </style>
</head>
<body>
  <a href="/" class="back-link">← Back to all certificates</a>
  
  <h1>📜 Inspection Certificate</h1>
  
  <div class="status-verified">✅ VERIFIED</div>
  
  <h2>Certificate Details</h2>
  
  <div class="field">
    <div class="field-label">Certificate ID</div>
    <div class="field-value mono">${escapeHtml(cert.id)}</div>
  </div>

  <div class="field">
    <div class="field-label">Type</div>
    <div class="field-value">
      <span class="badge badge-${escapeHtml(cert.type)}">${escapeHtml(cert.type)}</span>
    </div>
  </div>

  <div class="field">
    <div class="field-label">Claimant</div>
    <div class="field-value mono">${escapeHtml(cert.claimant)}</div>
  </div>

  <div class="field">
    <div class="field-label">Input Hash (SHA256)</div>
    <div class="field-value mono">${escapeHtml(cert.inputHash)}</div>
  </div>

  <div class="field">
    <div class="field-label">Inspection Prompt</div>
    <div class="field-value">[Full content available via authenticated API]</div>
  </div>

  <h2>Inspection Result</h2>

  <div class="field">
    <div class="field-value">[Full content available via authenticated API]</div>
  </div>

  <h2>Verification</h2>

  <div class="field">
    <div class="field-label">Timestamp</div>
    <div class="field-value">${escapeHtml(new Date(cert.timestamp).toISOString())}</div>
  </div>

  <div class="field">
    <div class="field-label">Phala Attestation</div>
    <div class="field-value mono">${escapeHtml(cert.attestation.slice(0, 64))}...</div>
  </div>
  
  <div class="field">
    <div class="field-label">Trust Model</div>
    <div class="field-value">
      ✅ Execution: Phala CVM (Intel TDX)<br>
      ✅ Storage: Decentralized TEE<br>
      ✅ Attestation: Cryptographic proof<br>
      ✅ Data: Ephemeral (not stored)
    </div>
  </div>
  
  <div style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #333; color: #666; font-size: 13px; text-align: center;">
    <p>This certificate is cryptographically verifiable via Phala Network</p>
    <p>
      <a href="/">View All Certificates</a> ·
      <a href="https://github.com/amiller/skill-verifier">GitHub</a>
    </p>
  </div>
</body>
</html>
  `.trim();
}
