// src/index.ts
import Anthropic from "@anthropic-ai/sdk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { classify, type RoutingDecision } from "./classifier.js";
import { ModelRegistry, type ModelConfig } from "./models.js";

// Type definitions (simplified for local plugin)
type OpenClawPlugin = any;
type LLMProvider = any;

export default function smartRouter(): OpenClawPlugin {
  let stats = {
    totalRoutes: 0,
    byTier: { SIMPLE: 0, MEDIUM: 0, COMPLEX: 0, REASONING: 0, ONDEMAND: 0 },
    byModel: {} as Record<string, number>,
    totalEstimatedCost: 0,
    fallbackCount: 0,
  };

  return {
    id: "@local/smart-router",
    name: "Smart Router",
    version: "1.0.0",

    async init(api: any) {
      console.log("🎯 Smart Router plugin initializing...");

      // Register as a provider
      api.registerProvider({
        id: "smart-router",
        name: "Smart Router (Auto)",
        
        async chatCompletion(request: any, context: any) {
          // Check for manual ONDEMAND override
          if (request.model === "smart-router/ondemand") {
            const ondemandModel = "anthropic/claude-opus-4.6";
            const modelConfig = ModelRegistry.get(ondemandModel);
            if (!modelConfig) {
              throw new Error(`Model not found: ${ondemandModel}`);
            }

            stats.totalRoutes++;
            stats.byTier.ONDEMAND++;
            stats.byModel[ondemandModel] = (stats.byModel[ondemandModel] || 0) + 1;

            console.log(`🎯 [ONDEMAND] ${ondemandModel} (manual override)`);

            return await routeToProvider(modelConfig, request, {
              tier: "ONDEMAND",
              confidence: 1.0,
              recommendedModel: ondemandModel,
              costEstimate: 0.09,
              reasoning: "Manual ONDEMAND selection",
            });
          }

          // Extract the actual query from messages
          const lastMessage = request.messages[request.messages.length - 1];
          const query = typeof lastMessage.content === 'string'
            ? lastMessage.content
            : lastMessage.content.map((c: any) => c.type === 'text' ? c.text : '').join(' ');

          // Classify the query
          const decision = classify(query);

          // Update stats
          stats.totalRoutes++;
          stats.byTier[decision.tier]++;
          stats.byModel[decision.recommendedModel] =
            (stats.byModel[decision.recommendedModel] || 0) + 1;
          stats.totalEstimatedCost += decision.costEstimate;

          // Log the routing decision
          console.log(
            `🎯 [${decision.tier}] ${decision.recommendedModel} ` +
            `(confidence: ${(decision.confidence * 100).toFixed(0)}%, ` +
            `cost: $${decision.costEstimate.toFixed(4)})`
          );

          // Get the selected model config
          const modelConfig = ModelRegistry.get(decision.recommendedModel);
          if (!modelConfig) {
            throw new Error(`Model not found: ${decision.recommendedModel}`);
          }

          // Route to the appropriate provider with fallback support
          try {
            const response = await routeToProvider(
              modelConfig,
              request,
              decision
            );

            // Add routing metadata to response
            if (response.usage) {
              (response as any).routingDecision = {
                tier: decision.tier,
                confidence: decision.confidence,
                originalModel: request.model,
                selectedModel: decision.recommendedModel,
                costEstimate: decision.costEstimate,
              };
            }

            return response;
          } catch (error) {
            // Fallback to Opus 4.6 if primary REASONING model fails
            if (decision.tier === "REASONING" && decision.fallbackModel) {
              console.log(
                `⚠️  ${decision.recommendedModel} failed, falling back to ${decision.fallbackModel}`
              );

              stats.fallbackCount++;
              stats.byModel[decision.fallbackModel] =
                (stats.byModel[decision.fallbackModel] || 0) + 1;

              const fallbackConfig = ModelRegistry.get(decision.fallbackModel);
              if (!fallbackConfig) {
                throw error; // Re-throw original error if fallback not found
              }

              const fallbackDecision: RoutingDecision = {
                tier: "ONDEMAND",
                confidence: decision.confidence,
                recommendedModel: decision.fallbackModel,
                costEstimate: decision.costEstimate,
                reasoning: decision.reasoning,
                fallbackModel: undefined,
              };

              const fallbackResponse = await routeToProvider(
                fallbackConfig,
                request,
                fallbackDecision
              );

              if (fallbackResponse.usage) {
                (fallbackResponse as any).routingDecision = {
                  tier: "ONDEMAND",
                  confidence: decision.confidence,
                  originalModel: request.model,
                  selectedModel: decision.fallbackModel,
                  fallbackReason: "Primary model failed",
                };
              }

              return fallbackResponse;
            }

            throw error;
          }
        },

        models: async () => [
          {
            id: "auto",
            name: "Smart Router (Auto)",
            contextWindow: 200000,
            capabilities: {
              streaming: true,
              functionCalling: true,
              vision: true,
            },
          },
          {
            id: "ondemand",
            name: "Smart Router (On-Demand - Opus 4.6)",
            contextWindow: 200000,
            capabilities: {
              streaming: true,
              functionCalling: true,
              vision: true,
            },
          },
        ],
      });

      // Add CLI command to show stats
      api.registerCommand({
        name: "router-stats",
        description: "Show smart router statistics",
        async execute() {
          console.log("\n📊 Smart Router Statistics");
          console.log(`   Total routes: ${stats.totalRoutes}`);
          console.log(`   Fallback triggers: ${stats.fallbackCount}`);
          console.log(`   Total estimated cost: $${stats.totalEstimatedCost.toFixed(4)}\n`);

          console.log("   By Tier:");
          for (const [tier, count] of Object.entries(stats.byTier)) {
            const pct = stats.totalRoutes > 0
              ? ((count / stats.totalRoutes) * 100).toFixed(1)
              : "0.0";
            console.log(`     ${tier}: ${count} (${pct}%)`);
          }

          console.log("\n   By Model:");
          const sorted = Object.entries(stats.byModel).sort((a, b) => b[1] - a[1]);
          for (const [model, count] of sorted) {
            const pct = stats.totalRoutes > 0
              ? ((count / stats.totalRoutes) * 100).toFixed(1)
              : "0.0";
            console.log(`     ${model}: ${count} (${pct}%)`);
          }
          console.log();
        },
      });

      console.log("✓ Smart Router ready - use model: smart-router/auto");
    },
  };
}

async function routeToProvider(
  modelConfig: ModelConfig,
  request: any,
  decision: RoutingDecision
): Promise<any> {
  const { provider, model } = modelConfig;

  switch (provider) {
    case "anthropic": {
      const apiKey = process.env.ANTHROPIC_API_KEY;
      if (!apiKey) throw new Error("ANTHROPIC_API_KEY not set");
      
      const client = new Anthropic({ apiKey });
      
      const response = await client.messages.create({
        model,
        max_tokens: request.max_tokens || 4096,
        messages: request.messages,
        stream: request.stream || false,
      });

      // Convert to OpenAI format
      return {
        id: response.id,
        object: "chat.completion",
        created: Date.now(),
        model: decision.recommendedModel,
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: response.content[0].type === "text" 
                ? response.content[0].text 
                : "",
            },
            finish_reason: response.stop_reason || "stop",
          },
        ],
        usage: {
          prompt_tokens: response.usage.input_tokens,
          completion_tokens: response.usage.output_tokens,
          total_tokens: response.usage.input_tokens + response.usage.output_tokens,
        },
      };
    }

    case "google": {
      const apiKey = process.env.GOOGLE_API_KEY;
      if (!apiKey) throw new Error("GOOGLE_API_KEY not set");
      
      const genAI = new GoogleGenerativeAI(apiKey);
      const geminiModel = genAI.getGenerativeModel({ model });
      
      // Convert OpenAI format to Gemini format
      const contents = request.messages.map((msg: any) => ({
        role: msg.role === "assistant" ? "model" : "user",
        parts: [{ text: msg.content }],
      }));

      const result = await geminiModel.generateContent({
        contents,
        generationConfig: {
          maxOutputTokens: request.max_tokens || 4096,
        },
      });

      const response = result.response;
      const text = response.text();

      // Convert to OpenAI format
      return {
        id: `gemini-${Date.now()}`,
        object: "chat.completion",
        created: Date.now(),
        model: decision.recommendedModel,
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: text,
            },
            finish_reason: "stop",
          },
        ],
        usage: {
          prompt_tokens: 0, // Gemini doesn't provide this
          completion_tokens: 0,
          total_tokens: 0,
        },
      };
    }

    case "synthetic": {
      const apiKey = process.env.SYNTHETIC_API_KEY;
      if (!apiKey) throw new Error("SYNTHETIC_API_KEY not set");

      // Kimi API (Moonshot AI) - OpenAI-compatible endpoint
      const baseUrl = process.env.SYNTHETIC_API_URL || "https://api.moonshot.cn/v1";

      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          messages: request.messages,
          max_tokens: request.max_tokens || 4096,
          temperature: request.temperature || 0.7,
          stream: request.stream || false,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Synthetic API error: ${response.status} - ${errorText}`);
      }

      const data: any = await response.json();
      return {
        ...data,
        model: decision.recommendedModel,
      };
    }

    case "local": {
      // Local Ollama model
      const ollamaUrl = process.env.OLLAMA_URL || "http://localhost:11434";

      // Convert messages to Ollama format
      const prompt = request.messages
        .map((msg: any) => `${msg.role}: ${msg.content}`)
        .join("\n\n");

      const response = await fetch(`${ollamaUrl}/api/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          prompt,
          stream: false,
        }),
      });

      const data: any = await response.json();

      // Convert to OpenAI format
      return {
        id: `local-${Date.now()}`,
        object: "chat.completion",
        created: Date.now(),
        model: decision.recommendedModel,
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: data.response,
            },
            finish_reason: "stop",
          },
        ],
        usage: {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
      };
    }

    default:
      throw new Error(`Unknown provider: ${provider}`);
  }
}
