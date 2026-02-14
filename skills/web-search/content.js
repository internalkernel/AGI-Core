#!/usr/bin/env node

import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";

const url = process.argv[2];

if (!url) {
	console.log("Usage: content.js <url>");
	console.log("\nExtracts readable content from a webpage as markdown.");
	console.log("Uses Tavily extract (primary) with Readability fallback.");
	console.log("\nExamples:");
	console.log("  content.js https://example.com/article");
	console.log("  content.js https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html");
	process.exit(1);
}

const tavilyKey = process.env.TAVILY_API_KEY;

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

async function extractWithTavily(url) {
	const response = await fetch("https://api.tavily.com/extract", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"Authorization": `Bearer ${tavilyKey}`,
		},
		body: JSON.stringify({
			urls: [url],
			format: "markdown",
		}),
	});

	if (!response.ok) {
		const text = await response.text();
		throw new Error(`Tavily extract error ${response.status}: ${text}`);
	}

	const data = await response.json();
	const result = data.results?.[0];
	if (result && result.raw_content) {
		return result.raw_content;
	}
	const failed = data.failed_results?.[0];
	if (failed) {
		throw new Error(`Tavily extract failed: ${failed.error}`);
	}
	throw new Error("Tavily extract returned no content");
}

async function extractWithReadability(url) {
	const response = await fetch(url, {
		headers: {
			"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.9",
		},
		signal: AbortSignal.timeout(15000),
	});

	if (!response.ok) {
		throw new Error(`HTTP ${response.status}: ${response.statusText}`);
	}

	const html = await response.text();
	const dom = new JSDOM(html, { url });
	const reader = new Readability(dom.window.document);
	const article = reader.parse();

	if (article && article.content) {
		let output = "";
		if (article.title) output += `# ${article.title}\n\n`;
		output += htmlToMarkdown(article.content);
		return output;
	}

	// Fallback: try to extract main content
	const fallbackDoc = new JSDOM(html, { url });
	const body = fallbackDoc.window.document;
	body.querySelectorAll("script, style, noscript, nav, header, footer, aside").forEach(el => el.remove());

	const title = body.querySelector("title")?.textContent?.trim();
	const main = body.querySelector("main, article, [role='main'], .content, #content") || body.body;

	const text = main?.innerHTML || "";
	if (text.trim().length > 100) {
		let output = "";
		if (title) output += `# ${title}\n\n`;
		output += htmlToMarkdown(text);
		return output;
	}

	throw new Error("Could not extract readable content from this page.");
}

try {
	let content;

	if (tavilyKey) {
		try {
			content = await extractWithTavily(url);
		} catch (e) {
			// Tavily failed, fall back to Readability
			content = await extractWithReadability(url);
		}
	} else {
		content = await extractWithReadability(url);
	}

	console.log(content);
} catch (e) {
	console.error(`Error: ${e.message}`);
	process.exit(1);
}
