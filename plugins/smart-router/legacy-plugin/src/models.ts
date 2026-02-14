// src/models.ts
export interface ModelConfig {
  provider: "anthropic" | "google" | "synthetic" | "local";
  model: string;
  inputCost: number;  // per 1M tokens
  outputCost: number; // per 1M tokens
}

export const ModelRegistry = new Map<string, ModelConfig>([
  // Anthropic - Latest Models
  ["anthropic/claude-opus-4.6", {
    provider: "anthropic",
    model: "claude-opus-4-6",
    inputCost: 15.00,
    outputCost: 75.00,
  }],
  ["anthropic/claude-opus-4.5", {
    provider: "anthropic",
    model: "claude-opus-4-5-20250514",
    inputCost: 15.00,
    outputCost: 75.00,
  }],
  ["anthropic/claude-sonnet-4.5", {
    provider: "anthropic",
    model: "claude-sonnet-4-5-20250929",
    inputCost: 3.00,
    outputCost: 15.00,
  }],
  ["anthropic/claude-haiku-4.5", {
    provider: "anthropic",
    model: "claude-haiku-4-5-20251001",
    inputCost: 0.80,
    outputCost: 4.00,
  }],

  // Google - Latest Gemini Models
  ["google/gemini-2.0-flash-exp", {
    provider: "google",
    model: "gemini-2.0-flash-exp",
    inputCost: 0.075,
    outputCost: 0.30,
  }],
  ["google/gemini-2.0-flash-thinking-exp", {
    provider: "google",
    model: "gemini-2.0-flash-thinking-exp",
    inputCost: 0.00,
    outputCost: 0.00,
  }],
  ["google/gemini-2.0-pro", {
    provider: "google",
    model: "gemini-2.0-pro",
    inputCost: 1.25,
    outputCost: 5.00,
  }],

  // Synthetic Models (Kimi/Moonshot AI)
  ["synthetic/kimi-2.5", {
    provider: "synthetic",
    model: "kimi-2.5",
    inputCost: 0.50,
    outputCost: 2.00,
  }],
  // Local Models
  ["local/mistral-7b", {
    provider: "local",
    model: "mistral:7b",
    inputCost: 0.00,
    outputCost: 0.00,
  }],
]);
