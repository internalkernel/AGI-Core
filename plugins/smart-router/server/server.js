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

// Timeout for upstream calls (5 minutes)
const UPSTREAM_TIMEOUT_MS = 300_000;

// ─── Tier → Model mapping ───────────────────────────────────────────────────
const TIER_MODELS = {
  SIMPLE:    { provider: "openai",    model: "gpt-4.1-nano" },
  MEDIUM:    { provider: "gemini",    model: "gemini-2.5-pro" },
  CODEX:     { provider: "openai",    model: "gpt-5.2-codex" },
  REASONING: { provider: "synthetic", model: "hf:moonshotai/Kimi-K2.5" },
  ONDEMAND:  { provider: "anthropic", model: "claude-opus-4-6" },
};

// ─── Content extraction helper ──────────────────────────────────────────────
function extractText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(c => c.type === "text" || c.text)
      .map(c => c.text || "")
      .join("\n");
  }
  return String(content || "");
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

function classify(query) {
  const q = query.toLowerCase();
  const len = query.length;

  const reasoningHits = PATTERNS.reasoning.filter(p => q.includes(p)).length;
  const codeHits = PATTERNS.code.filter(p => q.includes(p)).length;
  const simpleHits = PATTERNS.simple.filter(p => q.includes(p)).length;
  const technicalHits = PATTERNS.technical.filter(p => q.includes(p)).length;

  if (q.includes("/ondemand")) return "ONDEMAND";
  if (q.includes("/codex")) return "CODEX";
  if (reasoningHits >= 2) return "REASONING";
  if (len < 80 && simpleHits > 0 && codeHits === 0 && technicalHits === 0) return "SIMPLE";
  if (len < 30) return "SIMPLE";
  if (codeHits >= 3 || (codeHits >= 2 && technicalHits >= 1)) return "CODEX";
  if (codeHits >= 1 && len > 200) return "CODEX";
  if (technicalHits >= 1 || codeHits >= 1 || len > 150) return "MEDIUM";

  return "SIMPLE";
}

// ─── Provider Dispatch ──────────────────────────────────────────────────────

function prepareOllamaMessages(messages) {
  const ollamaMessages = [];

  const systemMsgs = messages.filter(m => m.role === "system");
  const nonSystemMsgs = messages.filter(m => m.role !== "system");

  if (systemMsgs.length > 0) {
    const fullSystem = systemMsgs.map(m => extractText(m.content)).join("\n");
    const trimmedSystem = fullSystem.length > 500
      ? "You are a helpful assistant. Answer concisely."
      : fullSystem;
    ollamaMessages.push({ role: "system", content: trimmedSystem });
  }

  const recentMessages = nonSystemMsgs.slice(-6);
  for (const msg of recentMessages) {
    ollamaMessages.push({
      role: msg.role === "assistant" ? "assistant" : "user",
      content: extractText(msg.content),
    });
  }

  return ollamaMessages;
}

async function callOllama(model, messages, maxTokens) {
  const ollamaMessages = prepareOllamaMessages(messages);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  try {
    const res = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: ollamaMessages,
        stream: false,
        options: {
          num_predict: maxTokens || 1024,
        },
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Ollama HTTP ${res.status}: ${errText}`);
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

function prepareAnthropicMessages(messages) {
  let systemPrompt = "";
  const anthropicMessages = [];

  for (const msg of messages) {
    const text = extractText(msg.content);
    if (msg.role === "system") {
      systemPrompt += text + "\n";
    } else {
      anthropicMessages.push({
        role: msg.role === "assistant" ? "assistant" : "user",
        content: text,
      });
    }
  }

  if (anthropicMessages.length === 0) {
    anthropicMessages.push({ role: "user", content: "Hello" });
  }
  if (anthropicMessages[0].role !== "user") {
    anthropicMessages.unshift({ role: "user", content: "." });
  }
  const merged = [];
  for (const msg of anthropicMessages) {
    if (merged.length > 0 && merged[merged.length - 1].role === msg.role) {
      merged[merged.length - 1].content += "\n\n" + msg.content;
    } else {
      merged.push({ ...msg });
    }
  }

  return { systemPrompt: systemPrompt.trim(), messages: merged };
}

async function callSynthetic(model, messages, maxTokens) {
  const client = new Anthropic({
    apiKey: SYNTHETIC_API_KEY,
    baseURL: SYNTHETIC_BASE_URL,
    timeout: UPSTREAM_TIMEOUT_MS,
  });

  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const params = {
    model,
    max_tokens: maxTokens || 4096,
    messages: prepared,
  };
  if (systemPrompt) params.system = systemPrompt;

  const response = await client.messages.create(params);

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

async function callAnthropic(model, messages, maxTokens) {
  const client = new Anthropic({
    apiKey: ANTHROPIC_API_KEY,
    timeout: UPSTREAM_TIMEOUT_MS,
  });

  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const params = {
    model,
    max_tokens: maxTokens || 4096,
    messages: prepared,
  };
  if (systemPrompt) params.system = systemPrompt;

  const response = await client.messages.create(params);

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

async function callGemini(model, messages, maxTokens) {
  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);

  const geminiMessages = [];
  if (systemPrompt) {
    geminiMessages.push({ role: "system", content: systemPrompt });
  }
  geminiMessages.push(...prepared);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

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
        max_tokens: maxTokens || 4096,
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Gemini HTTP ${res.status}: ${errText}`);
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

async function callOpenAI(model, messages, maxTokens) {
  const { systemPrompt, messages: prepared } = prepareAnthropicMessages(messages);
  const useResponses = model.includes("codex");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

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
        body: JSON.stringify({ model, input, max_output_tokens: maxTokens || 4096 }),
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
        body: JSON.stringify({ model, messages: openaiMessages, max_tokens: maxTokens || 4096 }),
        signal: controller.signal,
      });
    }

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`OpenAI HTTP ${res.status}: ${errText}`);
    }

    const data = await res.json();

    if (useResponses) {
      let text = "";
      if (data.output) {
        for (const item of data.output) {
          if (item.type === "message" && item.content) {
            for (const block of item.content) {
              if (block.type === "output_text") text += block.text;
            }
          }
        }
      }
      return { content: text, promptTokens: data.usage?.input_tokens || 0, completionTokens: data.usage?.output_tokens || 0 };
    } else {
      return { content: data.choices?.[0]?.message?.content || "", promptTokens: data.usage?.prompt_tokens || 0, completionTokens: data.usage?.completion_tokens || 0 };
    }
  } finally {
    clearTimeout(timeout);
  }
}

async function dispatch(tier, messages, maxTokens) {
  const target = TIER_MODELS[tier];
  if (!target) throw new Error(`Unknown tier: ${tier}`);

  switch (target.provider) {
    case "ollama":
      return await callOllama(target.model, messages, maxTokens);
    case "synthetic":
      return await callSynthetic(target.model, messages, maxTokens);
    case "gemini":
      return await callGemini(target.model, messages, maxTokens);
    case "openai":
      return await callOpenAI(target.model, messages, maxTokens);
    case "anthropic":
      return await callAnthropic(target.model, messages, maxTokens);
    default:
      throw new Error(`Unknown provider: ${target.provider}`);
  }
}

// ─── Response sanitizer ──────────────────────────────────────────────────────
// Some models (e.g. Kimi) emit raw tool-call markup tokens as plain text.
// Strip them so the client doesn't display garbage.
function sanitize(text) {
  let cleaned = text.replace(/<\|tool_calls_section_begin\|>[\s\S]*?<\|tool_calls_section_end\|>/g, "");
  cleaned = cleaned.replace(/<\|tool_call(?:s_section)?(?:_begin|_end|_argument_begin|_argument_end)?\|>/g, "");
  cleaned = cleaned.replace(/functions\.\w+:\d+/g, "");
  return cleaned.trim();
}

// ─── Request Stats ──────────────────────────────────────────────────────────
const stats = { total: 0, byTier: {}, errors: 0 };

// ─── HTTP Server (OpenAI-compatible) ────────────────────────────────────────

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", c => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  // Health check
  if (req.method === "GET" && (req.url === "/" || req.url === "/health")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", stats }));
    return;
  }

  // Models endpoint
  if (req.method === "GET" && (req.url === "/v1/models" || req.url === "/models")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      object: "list",
      data: [
        { id: "auto", object: "model", owned_by: "smart-router" },
        { id: "codex", object: "model", owned_by: "smart-router" },
        { id: "ondemand", object: "model", owned_by: "smart-router" },
      ],
    }));
    return;
  }

  // Chat completions endpoint
  if (req.method === "POST" && (req.url === "/v1/chat/completions" || req.url === "/chat/completions")) {
    const startTime = Date.now();
    try {
      const body = JSON.parse(await readBody(req));
      const messages = body.messages || [];
      const maxTokens = body.max_tokens || 4096;
      const requestedModel = body.model || "auto";
      const wantStream = body.stream === true;

      const lastUserMsg = [...messages].reverse().find(m => m.role === "user");
      const query = lastUserMsg ? extractText(lastUserMsg.content) : "";

      let tier;
      if (requestedModel === "ondemand") {
        tier = "ONDEMAND";
      } else if (requestedModel === "codex") {
        tier = "CODEX";
      } else {
        tier = classify(query);
      }

      stats.total++;
      stats.byTier[tier] = (stats.byTier[tier] || 0) + 1;

      const target = TIER_MODELS[tier];
      const queryPreview = query.slice(0, 80).replace(/\n/g, " ");
      console.log(`[${new Date().toISOString()}] REQ ${tier} → ${target.provider}/${target.model} | ${messages.length} msgs | stream=${wantStream} | "${queryPreview}"`);

      const raw = await dispatch(tier, messages, maxTokens);
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

        const CHUNK_SIZE = 20;
        const text = result.content;
        for (let i = 0; i < text.length; i += CHUNK_SIZE) {
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
          res.write(`data: ${JSON.stringify(chunk)}\n\n`);
        }

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

      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        error: { message: err.message, type: "server_error" },
      }));
    }
    return;
  }

  // 404
  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Smart Router server listening on http://127.0.0.1:${PORT}`);
  console.log(`Routing tiers:`);
  for (const [tier, target] of Object.entries(TIER_MODELS)) {
    console.log(`  ${tier.padEnd(10)} → ${target.provider}/${target.model}`);
  }
  console.log(`Upstream timeout: ${UPSTREAM_TIMEOUT_MS}ms`);
});
