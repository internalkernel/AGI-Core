import http from "node:http";
import Anthropic from "@anthropic-ai/sdk";

// ─── Configuration ──────────────────────────────────────────────────────────
const PORT = parseInt(process.env.ROUTER_PORT || "9999", 10);
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";
const SYNTHETIC_API_KEY = process.env.SYNTHETIC_API_KEY;
const SYNTHETIC_BASE_URL = "https://api.synthetic.new/anthropic";
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENAI_BASE_URL = "https://api.openai.com/v1";
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
const GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai";

// Auth: all non-health endpoints require Bearer token when set.
// Fail-closed: if not set, require explicit opt-out via ROUTER_ALLOW_UNAUTHENTICATED=true
const ROUTER_API_KEY = process.env.ROUTER_API_KEY || "";
const ALLOW_UNAUTHENTICATED = process.env.ROUTER_ALLOW_UNAUTHENTICATED === "true";

// Timeout for upstream calls (5 minutes)
const UPSTREAM_TIMEOUT_MS = 300_000;

// Request body size limit (2 MB) and read timeout (30s)
const MAX_BODY_BYTES = 2 * 1024 * 1024;
const BODY_READ_TIMEOUT_MS = 30_000;

// Concurrency: max in-flight requests
const MAX_CONCURRENT = 20;
let activeRequests = 0;

// Per-tier max_tokens caps (prevents callers from requesting excessive output)
const TIER_MAX_TOKENS = {
  SIMPLE:    1024,
  MEDIUM:    4096,
  COMPLEX:   4096,
  CODEX:     8192,
  REASONING: 4096,
  ONDEMAND:  8192,
};

// Input validation limits
const MAX_MESSAGES = 100;
const MAX_MESSAGE_CHARS = 100_000;   // per-message content limit
const MAX_TOTAL_INPUT_CHARS = 500_000; // total input cap across all messages
const VALID_ROLES = new Set(["system", "user", "assistant"]);

// ─── Tier → Model mapping ───────────────────────────────────────────────────
const TIER_MODELS = {
  SIMPLE:    { provider: "openai",    model: "gpt-4.1-nano" },
  MEDIUM:    { provider: "gemini",    model: "gemini-3.1-pro-preview" },
  COMPLEX:   { provider: "anthropic", model: "claude-sonnet-4-6" },
  CODEX:     { provider: "openai",    model: "gpt-5.2-codex" },
  REASONING: { provider: "synthetic", model: "hf:moonshotai/Kimi-K2.5" },
  ONDEMAND:  { provider: "anthropic", model: "claude-opus-4-6" },
};

// ─── Singleton SDK clients (reused across requests) ─────────────────────────
const syntheticClient = SYNTHETIC_API_KEY
  ? new Anthropic({ apiKey: SYNTHETIC_API_KEY, baseURL: SYNTHETIC_BASE_URL, timeout: UPSTREAM_TIMEOUT_MS })
  : null;

const anthropicClient = ANTHROPIC_API_KEY
  ? new Anthropic({ apiKey: ANTHROPIC_API_KEY, timeout: UPSTREAM_TIMEOUT_MS })
  : null;

// ─── Content extraction helper ──────────────────────────────────────────────
function extractText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(c => c && typeof c === "object" && (c.type === "text" || c.text))
      .map(c => c.text || "")
      .join("\n");
  }
  return String(content || "");
}

// ─── Input Validation + Normalization ────────────────────────────────────────
// Single pass: validate, extract text, capture last user text.
// Returns { error, normalized, lastUserText } — normalized is { role, text }[]
function validateAndNormalize(messages) {
  if (!Array.isArray(messages)) return { error: "messages must be an array" };
  if (messages.length === 0) return { error: "messages must not be empty" };
  if (messages.length > MAX_MESSAGES) return { error: `messages exceeds limit of ${MAX_MESSAGES}` };
  const normalized = [];
  let totalChars = 0;
  let lastUserText = "";
  for (const msg of messages) {
    if (typeof msg !== "object" || msg === null) return { error: "each message must be an object" };
    if (!VALID_ROLES.has(msg.role)) return { error: `invalid role: ${String(msg.role).slice(0, 20)}` };
    const text = extractText(msg.content);
    if (text.length > MAX_MESSAGE_CHARS) return { error: `message content exceeds ${MAX_MESSAGE_CHARS} char limit` };
    totalChars += text.length;
    if (totalChars > MAX_TOTAL_INPUT_CHARS) return { error: `total input exceeds ${MAX_TOTAL_INPUT_CHARS} char limit` };
    normalized.push({ role: msg.role, text });
    if (msg.role === "user") lastUserText = text;
  }
  return { error: null, normalized, lastUserText };
}

// ─── Query Classifier ───────────────────────────────────────────────────────
const PATTERNS = {
  reasoning: ["prove", "theorem", "proof", "demonstrate", "derive",
    "step by step", "step-by-step", "reasoning", "logic", "analyze",
    "compare and contrast", "evaluate", "critique"],
  code: ["function", "class", "import", "async", "await", "def ",
    "const ", "let ", "var ", "```", "algorithm", "implement", "code",
    "script", "debug", "refactor", "compile", "syntax"],
  simple: ["what is", "define", "translate", "hello", "hi", "hey",
    "how are", "thanks", "thank you", "yes", "no", "ok", "okay"],
  technical: ["kubernetes", "docker", "api", "database", "algorithm",
    "neural", "machine learning", "distributed", "architecture",
    "terraform", "nginx", "redis", "postgresql"],
};

function countHits(patterns, text) {
  let count = 0;
  for (const p of patterns) {
    if (text.includes(p)) count++;
  }
  return count;
}

const CLASSIFY_MAX_CHARS = 4000;
function classify(query) {
  // Only inspect the first N chars for classification — full prompt not needed for heuristics
  const prefix = query.length > CLASSIFY_MAX_CHARS ? query.slice(0, CLASSIFY_MAX_CHARS) : query;
  const q = prefix.toLowerCase();
  const len = query.length;

  const reasoningHits = countHits(PATTERNS.reasoning, q);
  const codeHits = countHits(PATTERNS.code, q);
  const simpleHits = countHits(PATTERNS.simple, q);
  const technicalHits = countHits(PATTERNS.technical, q);

  // Tier triggers removed from message content — only honored via model field
  if (reasoningHits >= 2) return "REASONING";
  if (len < 80 && simpleHits > 0 && codeHits === 0 && technicalHits === 0) return "SIMPLE";
  if (len < 30) return "SIMPLE";
  if (codeHits >= 3 || (codeHits >= 2 && technicalHits >= 1)) return "CODEX";
  if (codeHits >= 1 && len > 200) return "CODEX";
  if (technicalHits >= 1 || codeHits >= 1 || len > 150) return "MEDIUM";

  return "SIMPLE";
}

// ─── Provider Dispatch ──────────────────────────────────────────────────────

// All prepare* functions accept pre-normalized messages: { role, text }[]
function prepareOllamaMessages(normalized) {
  const ollamaMessages = [];

  const systemMsgs = normalized.filter(m => m.role === "system");
  const nonSystemMsgs = normalized.filter(m => m.role !== "system");

  if (systemMsgs.length > 0) {
    const fullSystem = systemMsgs.map(m => m.text).join("\n");
    const trimmedSystem = fullSystem.length > 500
      ? "You are a helpful assistant. Answer concisely."
      : fullSystem;
    ollamaMessages.push({ role: "system", content: trimmedSystem });
  }

  const recentMessages = nonSystemMsgs.slice(-6);
  for (const msg of recentMessages) {
    ollamaMessages.push({
      role: msg.role === "assistant" ? "assistant" : "user",
      content: msg.text,
    });
  }

  return ollamaMessages;
}

async function callOllama(model, messages, maxTokens, signal) {
  const ollamaMessages = prepareOllamaMessages(messages);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  // Abort upstream when client disconnects
  if (signal) signal.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    const res = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: ollamaMessages,
        stream: false,
        options: {
          num_predict: maxTokens,
        },
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      await drainErrorBody(res);
      console.error(`[${new Date().toISOString()}] Ollama upstream error: HTTP ${res.status}`);
      throw new Error("Upstream provider error");
    }

    const data = await res.json();

    return {
      content: data.message?.content || data.response || "",
      promptTokens: data.prompt_eval_count || 0,
      completionTokens: data.eval_count || 0,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function prepareAnthropicMessages(normalized) {
  const systemParts = [];
  const anthropicMessages = [];

  for (const msg of normalized) {
    if (msg.role === "system") {
      systemParts.push(msg.text);
    } else {
      anthropicMessages.push({
        role: msg.role === "assistant" ? "assistant" : "user",
        content: msg.text,
      });
    }
  }

  if (anthropicMessages.length === 0) {
    anthropicMessages.push({ role: "user", content: "Hello" });
  }
  if (anthropicMessages[0].role !== "user") {
    anthropicMessages.unshift({ role: "user", content: "." });
  }
  // Merge consecutive same-role messages using array accumulation (avoids O(n^2) string concat)
  const merged = [];
  for (const msg of anthropicMessages) {
    if (merged.length > 0 && merged[merged.length - 1].role === msg.role) {
      merged[merged.length - 1]._parts.push(msg.content);
    } else {
      merged.push({ role: msg.role, content: msg.content, _parts: [msg.content] });
    }
  }
  for (const m of merged) {
    if (m._parts.length > 1) m.content = m._parts.join("\n\n");
    delete m._parts;
  }

  return { systemPrompt: systemParts.join("\n").trim(), messages: merged };
}

async function callSynthetic(model, messages, maxTokens, signal) {
  if (!syntheticClient) throw new Error("Synthetic provider not configured");

  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const params = {
    model,
    max_tokens: maxTokens,
    messages: prepared,
  };
  if (systemPrompt) params.system = systemPrompt;

  // Abort upstream when client disconnects
  const options = {};
  if (signal) options.signal = signal;

  const response = await syntheticClient.messages.create(params, options);

  const text = response.content
    .filter(c => c.type === "text")
    .map(c => c.text)
    .join("");

  return {
    content: text,
    promptTokens: response.usage?.input_tokens || 0,
    completionTokens: response.usage?.output_tokens || 0,
  };
}

// Minimum token estimate for Anthropic prompt caching (1024 tokens ≈ 4KB text)
const CACHE_MIN_CHARS = 4000;

async function callAnthropic(model, messages, maxTokens, signal) {
  if (!anthropicClient) throw new Error("Anthropic provider not configured");

  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const params = {
    model,
    max_tokens: maxTokens,
    messages: prepared,
  };

  // Prompt caching: send system prompt as a cached content block (90% savings on reads)
  if (systemPrompt && systemPrompt.length >= CACHE_MIN_CHARS) {
    params.system = [{ type: "text", text: systemPrompt, cache_control: { type: "ephemeral" } }];
  } else if (systemPrompt) {
    params.system = systemPrompt;
  }

  // Cache conversation history: mark the second-to-last message as a cache breakpoint
  // so all prior turns are cached across consecutive calls
  if (prepared.length >= 2) {
    const target = prepared[prepared.length - 2];
    if (typeof target.content === "string" && target.content.length >= CACHE_MIN_CHARS) {
      target.content = [{ type: "text", text: target.content, cache_control: { type: "ephemeral" } }];
    }
  }

  // Abort upstream when client disconnects
  const options = {};
  if (signal) options.signal = signal;

  const response = await anthropicClient.messages.create(params, options);

  const text = response.content
    .filter(c => c.type === "text")
    .map(c => c.text)
    .join("");

  const usage = response.usage || {};
  const cacheRead = usage.cache_read_input_tokens || 0;
  const cacheWrite = usage.cache_creation_input_tokens || 0;
  if (cacheRead || cacheWrite) {
    console.log(`[${new Date().toISOString()}] CACHE ${model} | read=${cacheRead} write=${cacheWrite} tokens`);
  }

  return {
    content: text,
    promptTokens: usage.input_tokens || 0,
    completionTokens: usage.output_tokens || 0,
  };
}

async function callGemini(model, messages, maxTokens, signal) {
  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const geminiMessages = [];
  if (systemPrompt) {
    geminiMessages.push({ role: "system", content: systemPrompt });
  }
  geminiMessages.push(...prepared);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  // Abort upstream when client disconnects
  if (signal) signal.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    const res = await fetch(`${GEMINI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${GOOGLE_API_KEY}`,
      },
      body: JSON.stringify({
        model,
        messages: geminiMessages,
        max_tokens: maxTokens,
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      await drainErrorBody(res);
      console.error(`[${new Date().toISOString()}] Gemini upstream error: HTTP ${res.status}`);
      throw new Error("Upstream provider error");
    }

    const data = await res.json();
    const text = data.choices?.[0]?.message?.content || "";

    return {
      content: text,
      promptTokens: data.usage?.prompt_tokens || 0,
      completionTokens: data.usage?.completion_tokens || 0,
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function callOpenAI(model, messages, maxTokens, signal) {
  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);
  const useResponses = model.includes("codex");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  // Abort upstream when client disconnects
  if (signal) signal.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    let res;
    if (useResponses) {
      // Codex models require the /v1/responses endpoint
      const input = [];
      if (systemPrompt) input.push({ role: "developer", content: systemPrompt });
      for (const msg of prepared) {
        input.push({ role: msg.role === "assistant" ? "assistant" : "user", content: msg.content });
      }
      res = await fetch(`${OPENAI_BASE_URL}/responses`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${OPENAI_API_KEY}` },
        body: JSON.stringify({ model, input, max_output_tokens: maxTokens }),
        signal: controller.signal,
      });
    } else {
      // Standard models use /v1/chat/completions
      const openaiMessages = [];
      if (systemPrompt) openaiMessages.push({ role: "system", content: systemPrompt });
      openaiMessages.push(...prepared);
      res = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${OPENAI_API_KEY}` },
        body: JSON.stringify({ model, messages: openaiMessages, max_tokens: maxTokens }),
        signal: controller.signal,
      });
    }

    if (!res.ok) {
      await drainErrorBody(res);
      console.error(`[${new Date().toISOString()}] OpenAI upstream error: HTTP ${res.status}`);
      throw new Error("Upstream provider error");
    }

    const data = await res.json();

    if (useResponses) {
      const textParts = [];
      if (data.output) {
        for (const item of data.output) {
          if (item.type === "message" && item.content) {
            for (const block of item.content) {
              if (block.type === "output_text") textParts.push(block.text);
            }
          }
        }
      }
      return { content: textParts.join(""), promptTokens: data.usage?.input_tokens || 0, completionTokens: data.usage?.output_tokens || 0 };
    } else {
      return { content: data.choices?.[0]?.message?.content || "", promptTokens: data.usage?.prompt_tokens || 0, completionTokens: data.usage?.completion_tokens || 0 };
    }
  } finally {
    clearTimeout(timeout);
  }
}

async function dispatch(tier, messages, maxTokens, signal) {
  const target = TIER_MODELS[tier];
  if (!target) throw new Error(`Unknown tier: ${tier}`);

  switch (target.provider) {
    case "ollama":
      return await callOllama(target.model, messages, maxTokens, signal);
    case "synthetic":
      return await callSynthetic(target.model, messages, maxTokens, signal);
    case "gemini":
      return await callGemini(target.model, messages, maxTokens, signal);
    case "openai":
      return await callOpenAI(target.model, messages, maxTokens, signal);
    case "anthropic":
      return await callAnthropic(target.model, messages, maxTokens, signal);
    default:
      throw new Error(`Unknown provider: ${target.provider}`);
  }
}

// ─── Upstream error body drain (capped to avoid memory amplification) ────────
async function drainErrorBody(res) {
  try { res.body?.cancel(); } catch { /* ignore */ }
}

// ─── Response sanitizer ──────────────────────────────────────────────────────
// Some models (e.g. Kimi) emit raw tool-call markup tokens as plain text.
// Strip them so the client doesn't display garbage.
function sanitize(text) {
  // Fast path: skip regex passes if no tool-markup tokens present
  if (!text.includes("<|") && !text.includes("functions.")) return text.trim();
  let cleaned = text.replace(/<\|tool_calls_section_begin\|>[\s\S]*?<\|tool_calls_section_end\|>/g, "");
  cleaned = cleaned.replace(/<\|tool_call(?:s_section)?(?:_begin|_end|_argument_begin|_argument_end)?\|>/g, "");
  cleaned = cleaned.replace(/functions\.\w+:\d+/g, "");
  return cleaned.trim();
}

// ─── Request Stats (bounded) ────────────────────────────────────────────────
const stats = { total: 0, byTier: {}, errors: 0 };

// ─── Auth helper ────────────────────────────────────────────────────────────
function checkAuth(req) {
  if (!ROUTER_API_KEY) return ALLOW_UNAUTHENTICATED;
  const auth = req.headers["authorization"];
  if (!auth) return false;
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  // Constant-time comparison to prevent timing attacks
  if (token.length !== ROUTER_API_KEY.length) return false;
  let mismatch = 0;
  for (let i = 0; i < token.length; i++) {
    mismatch |= token.charCodeAt(i) ^ ROUTER_API_KEY.charCodeAt(i);
  }
  return mismatch === 0;
}

// ─── HTTP Server (OpenAI-compatible) ────────────────────────────────────────

function readBody(req) {
  return new Promise((resolve, reject) => {
    // Early reject via Content-Length if available
    const contentLength = parseInt(req.headers["content-length"], 10);
    if (contentLength > MAX_BODY_BYTES) {
      req.destroy();
      return reject(new Error("Request body too large"));
    }

    let settled = false;
    let timer;
    const fail = (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      req.destroy();
      reject(err);
    };

    // Body read timeout prevents slow-body DoS
    timer = setTimeout(() => fail(new Error("Request body read timeout")), BODY_READ_TIMEOUT_MS);

    const chunks = [];
    let bytes = 0;
    req.on("data", (c) => {
      bytes += c.length;
      if (bytes > MAX_BODY_BYTES) {
        fail(new Error("Request body too large"));
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(Buffer.concat(chunks).toString());
    });
    req.on("error", (err) => fail(err));
    req.on("aborted", () => fail(new Error("Request aborted")));
    req.on("close", () => {
      if (!settled) fail(new Error("Request closed"));
    });
  });
}

const server = http.createServer(async (req, res) => {
  // Health check (no auth required)
  if (req.method === "GET" && (req.url === "/" || req.url === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  // Auth check for all non-health endpoints
  if (!checkAuth(req)) {
    res.writeHead(401, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: { message: "Unauthorized", type: "auth_error" } }));
    return;
  }

  // Models endpoint
  if (req.method === "GET" && (req.url === "/v1/models" || req.url === "/models")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      object: "list",
      data: [
        { id: "auto", object: "model", owned_by: "smart-router" },
        { id: "complex", object: "model", owned_by: "smart-router" },
        { id: "codex", object: "model", owned_by: "smart-router" },
        { id: "ondemand", object: "model", owned_by: "smart-router" },
      ],
    }));
    return;
  }

  // Chat completions endpoint
  if (req.method === "POST" && (req.url === "/v1/chat/completions" || req.url === "/chat/completions")) {
    // Concurrency guard
    if (activeRequests >= MAX_CONCURRENT) {
      res.writeHead(429, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: { message: "Too many requests", type: "rate_limit_error" } }));
      return;
    }
    activeRequests++;

    // Track client disconnect so we can abort upstream calls
    // Use res "close" with writableEnded guard — req "close" fires on normal completion too
    const clientAbort = new AbortController();
    res.on("close", () => { if (!res.writableEnded) clientAbort.abort(); });

    const startTime = Date.now();
    try {
      let body;
      try {
        body = JSON.parse(await readBody(req));
      } catch (parseErr) {
        if (parseErr instanceof SyntaxError) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: { message: "Malformed JSON", type: "invalid_request_error" } }));
          return;
        }
        throw parseErr; // re-throw non-JSON errors (readBody timeout, etc.)
      }
      const requestedModel = body.model || "auto";
      const wantStream = body.stream === true;

      // Single-pass validate + normalize + extract lastUserText
      const { error: validationError, normalized, lastUserText } = validateAndNormalize(body.messages);
      if (validationError) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: { message: validationError, type: "invalid_request_error" } }));
        return;
      }

      const query = lastUserText;

      let tier;
      if (requestedModel === "ondemand") {
        tier = "ONDEMAND";
      } else if (requestedModel === "complex") {
        tier = "COMPLEX";
      } else if (requestedModel === "codex") {
        tier = "CODEX";
      } else {
        tier = classify(query);
      }

      // Validate and clamp max_tokens to per-tier cap
      const tierCap = TIER_MAX_TOKENS[tier] || 4096;
      let rawMax = body.max_tokens;
      if (rawMax !== undefined && rawMax !== null) {
        rawMax = Number(rawMax);
        if (!Number.isFinite(rawMax) || rawMax < 1) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: { message: "max_tokens must be a positive integer", type: "invalid_request_error" } }));
          return;
        }
        rawMax = Math.floor(rawMax);
      }
      const maxTokens = Math.min(rawMax || tierCap, tierCap);

      stats.total++;
      stats.byTier[tier] = (stats.byTier[tier] || 0) + 1;

      const target = TIER_MODELS[tier];
      console.log(`[${new Date().toISOString()}] REQ ${tier} → ${target.provider}/${target.model} | ${normalized.length} msgs | stream=${wantStream}`);

      const raw = await dispatch(tier, normalized, maxTokens, clientAbort.signal);
      raw.content = sanitize(raw.content);
      const result = raw;
      const durationMs = Date.now() - startTime;

      console.log(`[${new Date().toISOString()}] OK  ${tier} | ${durationMs}ms | ${result.content.length} chars`);

      const completionId = `chatcmpl-${Date.now()}`;
      const created = Math.floor(Date.now() / 1000);

      if (wantStream) {
        // ── SSE streaming response ──
        res.writeHead(200, {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        });

        const roleChunk = {
          id: completionId,
          object: "chat.completion.chunk",
          created,
          model: `smart-router/${requestedModel}`,
          choices: [{
            index: 0,
            delta: { role: "assistant", content: "" },
            finish_reason: null,
          }],
        };
        res.write(`data: ${JSON.stringify(roleChunk)}\n\n`);

        // Larger chunks (512 chars) with abort-aware backpressure
        const CHUNK_SIZE = 512;
        const DRAIN_TIMEOUT_MS = 10_000;
        const text = result.content;
        for (let i = 0; i < text.length; i += CHUNK_SIZE) {
          if (clientAbort.signal.aborted) break;
          const piece = text.slice(i, i + CHUNK_SIZE);
          const chunk = {
            id: completionId,
            object: "chat.completion.chunk",
            created,
            model: `smart-router/${requestedModel}`,
            choices: [{
              index: 0,
              delta: { content: piece },
              finish_reason: null,
            }],
          };
          const canContinue = res.write(`data: ${JSON.stringify(chunk)}\n\n`);
          if (!canContinue) {
            // Wait for drain OR client disconnect OR timeout — with proper cleanup
            const drained = await new Promise((resolve) => {
              let done = false;
              const settle = (val) => { if (done) return; done = true; cleanup(); resolve(val); };
              const onDrain = () => settle(true);
              const onAbort = () => settle(false);
              const timer = setTimeout(() => settle(false), DRAIN_TIMEOUT_MS);
              const cleanup = () => {
                clearTimeout(timer);
                res.removeListener("drain", onDrain);
                clientAbort.signal.removeEventListener("abort", onAbort);
              };
              res.once("drain", onDrain);
              if (clientAbort.signal.aborted) { settle(false); return; }
              clientAbort.signal.addEventListener("abort", onAbort, { once: true });
            });
            if (!drained) break;
          }
        }

        if (!clientAbort.signal.aborted) {
          if (body.stream_options?.include_usage) {
            const usageChunk = {
              id: completionId,
              object: "chat.completion.chunk",
              created,
              model: `smart-router/${requestedModel}`,
              choices: [],
              usage: {
                prompt_tokens: result.promptTokens,
                completion_tokens: result.completionTokens,
                total_tokens: result.promptTokens + result.completionTokens,
              },
            };
            res.write(`data: ${JSON.stringify(usageChunk)}\n\n`);
          }

          const finishChunk = {
            id: completionId,
            object: "chat.completion.chunk",
            created,
            model: `smart-router/${requestedModel}`,
            choices: [{
              index: 0,
              delta: {},
              finish_reason: "stop",
            }],
          };
          res.write(`data: ${JSON.stringify(finishChunk)}\n\n`);

          res.write("data: [DONE]\n\n");
        }
        res.end();
      } else {
        // ── Non-streaming JSON response ──
        const response = {
          id: completionId,
          object: "chat.completion",
          created,
          model: `smart-router/${requestedModel}`,
          choices: [{
            index: 0,
            message: { role: "assistant", content: result.content },
            finish_reason: "stop",
          }],
          usage: {
            prompt_tokens: result.promptTokens,
            completion_tokens: result.completionTokens,
            total_tokens: result.promptTokens + result.completionTokens,
          },
        };

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(response));
      }
    } catch (err) {
      stats.errors++;
      const durationMs = Date.now() - startTime;
      console.error(`[${new Date().toISOString()}] ERR ${durationMs}ms |`, err.message);
      if (err.cause) console.error(`  cause:`, err.cause.message || err.cause);

      if (!res.headersSent) {
        let statusCode = 500;
        let clientMsg = "Internal server error";
        if (err.message === "Request body too large") { statusCode = 413; clientMsg = "Request body too large"; }
        else if (err.message === "Request body read timeout") { statusCode = 408; clientMsg = "Request timeout"; }
        res.writeHead(statusCode, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          error: { message: clientMsg, type: "server_error" },
        }));
      }
    } finally {
      activeRequests--;
    }
    return;
  }

  // 404
  res.writeHead(404);
  res.end("Not found");
});

// Server-level timeouts to prevent slow-client DoS
server.headersTimeout = 10_000;     // 10s to receive headers
server.requestTimeout = 60_000;     // 60s total request lifetime
server.keepAliveTimeout = 30_000;   // 30s idle keep-alive

server.listen(PORT, "127.0.0.1", () => {
  const authStatus = ROUTER_API_KEY
    ? "enabled (ROUTER_API_KEY set)"
    : ALLOW_UNAUTHENTICATED
      ? "disabled (ROUTER_ALLOW_UNAUTHENTICATED=true)"
      : "BLOCKED (no ROUTER_API_KEY — set one or use ROUTER_ALLOW_UNAUTHENTICATED=true)";
  console.log(`Smart Router server listening on http://127.0.0.1:${PORT}`);
  console.log(`Auth: ${authStatus}`);
  console.log(`Routing tiers:`);
  for (const [tier, target] of Object.entries(TIER_MODELS)) {
    console.log(`  ${tier.padEnd(10)} → ${target.provider}/${target.model} (max_tokens: ${TIER_MAX_TOKENS[tier]})`);
  }
  console.log(`Upstream timeout: ${UPSTREAM_TIMEOUT_MS}ms`);
  console.log(`Max concurrent requests: ${MAX_CONCURRENT}`);
  console.log(`Max body size: ${MAX_BODY_BYTES} bytes`);
  console.log(`Body read timeout: ${BODY_READ_TIMEOUT_MS}ms`);
});
