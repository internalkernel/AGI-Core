#!/usr/bin/env node

import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

const args = process.argv.slice(2);

const contentIndex = args.indexOf("--content");
const fetchContent = contentIndex !== -1;
if (fetchContent) args.splice(contentIndex, 1);

let numResults = 5;
const nIndex = args.indexOf("-n");
if (nIndex !== -1 && args[nIndex + 1]) {
	numResults = parseInt(args[nIndex + 1], 10);
	args.splice(nIndex, 2);
}

const query = args.join(" ");

if (!query) {
	console.log("Usage: search.js <query> [-n <num>] [--content]");
	console.log("\nOptions:");
	console.log("  -n <num>    Number of results (default: 5)");
	console.log("  --content   Fetch readable content as markdown");
	console.log("\nExamples:");
	console.log('  search.js "javascript async await"');
	console.log('  search.js "rust programming" -n 10');
	console.log('  search.js "climate change" --content');
	process.exit(1);
}

const apiKey = process.env.BRAVE_SEARCH_API_KEY;
if (!apiKey) {
	console.error("Error: BRAVE_SEARCH_API_KEY environment variable not set.");
	console.error("Get an API key from https://brave.com/search/api/");
	process.exit(1);
}

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
				"X-Subscription-Token": apiKey,
			},
		}
	);

	if (!response.ok) {
		const body = await response.text();
		throw new Error(`Brave API error ${response.status}: ${body}`);
	}

	const data = await response.json();
	const webResults = data.web?.results || [];

	return webResults.slice(0, numResults).map((r) => ({
		title: r.title || "",
		link: r.url || "",
		snippet: r.description || "",
	}));
}

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
		
		// Fallback: try to get main content
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

// Main
try {
	const results = await fetchBraveResults(query, numResults);
	
	if (results.length === 0) {
		console.error("No results found.");
		process.exit(0);
	}
	
	if (fetchContent) {
		for (const result of results) {
			result.content = await fetchPageContent(result.link);
		}
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
