#!/usr/bin/env node

import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

const args = process.argv.slice(2);

const contentIndex = args.indexOf("--content");
const fetchContent = contentIndex !== -1;
if (fetchContent) args.splice(contentIndex, 1);

let forcedEngine = null;
const engineIndex = args.indexOf("--engine");
if (engineIndex !== -1 && args[engineIndex + 1]) {
	forcedEngine = args[engineIndex + 1].toLowerCase();
	args.splice(engineIndex, 2);
}

let numResults = 5;
const nIndex = args.indexOf("-n");
if (nIndex !== -1 && args[nIndex + 1]) {
	numResults = parseInt(args[nIndex + 1], 10);
	args.splice(nIndex, 2);
}

const query = args.join(" ");

if (!query) {
	console.log("Usage: search.js <query> [-n <num>] [--content] [--engine tavily|brave]");
	console.log("\nOptions:");
	console.log("  -n <num>              Number of results (default: 5)");
	console.log("  --content             Fetch readable content as markdown");
	console.log("  --engine tavily|brave  Force a specific search engine (default: auto)");
	console.log("\nExamples:");
	console.log('  search.js "javascript async await"');
	console.log('  search.js "rust programming" -n 10');
	console.log('  search.js "climate change" --content');
	console.log('  search.js "news today" --engine brave');
	process.exit(1);
}

const tavilyKey = process.env.TAVILY_API_KEY;
const braveKey = process.env.BRAVE_SEARCH_API_KEY;

function pickEngine() {
	if (forcedEngine === "tavily") {
		if (!tavilyKey) {
			console.error("Error: --engine tavily requires TAVILY_API_KEY environment variable.");
			process.exit(1);
		}
		return "tavily";
	}
	if (forcedEngine === "brave") {
		if (!braveKey) {
			console.error("Error: --engine brave requires BRAVE_SEARCH_API_KEY environment variable.");
			process.exit(1);
		}
		return "brave";
	}
	if (tavilyKey) return "tavily";
	if (braveKey) return "brave";
	console.error("Error: No search API key found.");
	console.error("Set TAVILY_API_KEY (primary) or BRAVE_SEARCH_API_KEY (fallback).");
	process.exit(1);
}

// --- Tavily ---

async function fetchTavilyResults(query, numResults, includeContent) {
	const body = {
		query,
		max_results: Math.min(numResults, 20),
		include_answer: "basic",
	};
	if (includeContent) {
		body.include_raw_content = "markdown";
	}

	const response = await fetch("https://api.tavily.com/search", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"Authorization": `Bearer ${tavilyKey}`,
		},
		body: JSON.stringify(body),
	});

	if (!response.ok) {
		const text = await response.text();
		throw new Error(`Tavily API error ${response.status}: ${text}`);
	}

	const data = await response.json();
	const answer = data.answer || null;
	const results = (data.results || []).slice(0, numResults).map((r) => ({
		title: r.title || "",
		link: r.url || "",
		snippet: r.content || "",
		content: includeContent ? (r.raw_content || "").substring(0, 5000) : undefined,
	}));

	return { answer, results };
}

// --- Brave ---

async function fetchBraveResults(query, numResults) {
	const params = new URLSearchParams({
		q: query,
		count: String(Math.min(numResults, 20)),
	});

	const response = await fetch(
		`https://api.search.brave.com/res/v1/web/search?${params}`,
		{
			headers: {
				"Accept": "application/json",
				"Accept-Encoding": "gzip",
				"X-Subscription-Token": braveKey,
			},
		}
	);

	if (!response.ok) {
		const body = await response.text();
		throw new Error(`Brave API error ${response.status}: ${body}`);
	}

	const data = await response.json();
	const webResults = data.web?.results || [];

	return {
		answer: null,
		results: webResults.slice(0, numResults).map((r) => ({
			title: r.title || "",
			link: r.url || "",
			snippet: r.description || "",
		})),
	};
}

// --- Content extraction (for Brave --content) ---

function htmlToMarkdown(html) {
	const turndown = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });
	turndown.use(gfm);
	turndown.addRule("removeEmptyLinks", {
		filter: (node) => node.nodeName === "A" && !node.textContent?.trim(),
		replacement: () => "",
	});
	return turndown
		.turndown(html)
		.replace(/\[\\?\[\s*\\?\]\]\([^)]*\)/g, "")
		.replace(/ +/g, " ")
		.replace(/\s+,/g, ",")
		.replace(/\s+\./g, ".")
		.replace(/\n{3,}/g, "\n\n")
		.trim();
}

async function fetchPageContent(url) {
	try {
		const response = await fetch(url, {
			headers: {
				"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
				"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			},
			signal: AbortSignal.timeout(10000),
		});

		if (!response.ok) {
			return `(HTTP ${response.status})`;
		}

		const html = await response.text();
		const dom = new JSDOM(html, { url });
		const reader = new Readability(dom.window.document);
		const article = reader.parse();

		if (article && article.content) {
			return htmlToMarkdown(article.content).substring(0, 5000);
		}

		const fallbackDoc = new JSDOM(html, { url });
		const body = fallbackDoc.window.document;
		body.querySelectorAll("script, style, noscript, nav, header, footer, aside").forEach(el => el.remove());
		const main = body.querySelector("main, article, [role='main'], .content, #content") || body.body;
		const text = main?.textContent || "";

		if (text.trim().length > 100) {
			return text.trim().substring(0, 5000);
		}

		return "(Could not extract content)";
	} catch (e) {
		return `(Error: ${e.message})`;
	}
}

// --- Main ---

try {
	const engine = pickEngine();
	let answer, results;

	if (engine === "tavily") {
		({ answer, results } = await fetchTavilyResults(query, numResults, fetchContent));
	} else {
		({ answer, results } = await fetchBraveResults(query, numResults));
		if (fetchContent) {
			for (const result of results) {
				result.content = await fetchPageContent(result.link);
			}
		}
	}

	if (results.length === 0) {
		console.error("No results found.");
		process.exit(0);
	}

	if (answer) {
		console.log(`Answer: ${answer}\n`);
	}

	for (let i = 0; i < results.length; i++) {
		const r = results[i];
		console.log(`--- Result ${i + 1} ---`);
		console.log(`Title: ${r.title}`);
		console.log(`Link: ${r.link}`);
		console.log(`Snippet: ${r.snippet}`);
		if (r.content) {
			console.log(`Content:\n${r.content}`);
		}
		console.log("");
	}
} catch (e) {
	console.error(`Error: ${e.message}`);
	process.exit(1);
}
