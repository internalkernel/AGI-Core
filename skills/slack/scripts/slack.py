#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "slack-sdk>=3.27.0",
# ]
# ///
"""
Slack CLI tool for agents — react, pin, send/edit/delete messages, read channels, and fetch member info.

Usage:
    uv run slack.py <action> [options]

Requires SLACK_BOT_TOKEN env var (xoxb-...) with appropriate scopes.
"""

import argparse
import json
import os
import sys


def get_client():
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable not set.", file=sys.stderr)
        print("Set it to your Slack bot token (xoxb-...).", file=sys.stderr)
        sys.exit(1)
    return WebClient(token=token), SlackApiError


def main():
    parser = argparse.ArgumentParser(description="Slack CLI for agents")
    sub = parser.add_subparsers(dest="action", required=True)

    # react
    p = sub.add_parser("react", help="Add emoji reaction to a message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp (e.g. 1712023032.1234)")
    p.add_argument("--emoji", "-e", required=True, help="Emoji name without colons (e.g. white_check_mark)")

    # reactions
    p = sub.add_parser("reactions", help="List reactions on a message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp")

    # send
    p = sub.add_parser("send", help="Send a message to a channel or user")
    p.add_argument("--to", required=True, help="Target: channel ID or user ID")
    p.add_argument("--text", "-t", required=True, help="Message text")
    p.add_argument("--thread", help="Thread timestamp to reply to")

    # edit
    p = sub.add_parser("edit", help="Edit a bot message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp")
    p.add_argument("--text", "-t", required=True, help="New message text")

    # delete
    p = sub.add_parser("delete", help="Delete a bot message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp")

    # read
    p = sub.add_parser("read", help="Read recent messages from a channel")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--limit", "-l", type=int, default=20, help="Number of messages (default: 20)")
    p.add_argument("--thread", help="Thread timestamp to read replies from")

    # pin
    p = sub.add_parser("pin", help="Pin a message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp")

    # unpin
    p = sub.add_parser("unpin", help="Unpin a message")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")
    p.add_argument("--message", "-m", required=True, help="Message timestamp")

    # pins
    p = sub.add_parser("pins", help="List pinned items in a channel")
    p.add_argument("--channel", "-c", required=True, help="Channel ID")

    # member-info
    p = sub.add_parser("member-info", help="Get info about a Slack user")
    p.add_argument("--user", "-u", required=True, help="User ID")

    # channels
    p = sub.add_parser("channels", help="List channels the bot is in")
    p.add_argument("--limit", "-l", type=int, default=100, help="Number of channels (default: 100)")

    # search
    p = sub.add_parser("search", help="Search messages (requires user token with search:read)")
    p.add_argument("--query", "-q", required=True, help="Search query")
    p.add_argument("--limit", "-l", type=int, default=20, help="Number of results (default: 20)")

    # emoji-list
    sub.add_parser("emoji-list", help="List custom emoji in the workspace")

    args = parser.parse_args()
    client, SlackApiError = get_client()

    try:
        result = dispatch(client, args)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except SlackApiError as e:
        print(json.dumps({"ok": False, "error": str(e.response["error"])}, indent=2), file=sys.stderr)
        sys.exit(1)


def dispatch(client, args):
    action = args.action

    if action == "react":
        # Strip colons if provided
        emoji = args.emoji.strip(":")
        resp = client.reactions_add(channel=args.channel, timestamp=args.message, name=emoji)
        return {"ok": True, "action": "react", "emoji": emoji}

    elif action == "reactions":
        resp = client.reactions_get(channel=args.channel, timestamp=args.message)
        msg = resp["message"]
        reactions = msg.get("reactions", [])
        return {
            "ok": True,
            "reactions": [
                {"emoji": r["name"], "count": r["count"], "users": r["users"]}
                for r in reactions
            ],
        }

    elif action == "send":
        kwargs = {"channel": args.to, "text": args.text}
        if args.thread:
            kwargs["thread_ts"] = args.thread
        resp = client.chat_postMessage(**kwargs)
        return {
            "ok": True,
            "channel": resp["channel"],
            "messageId": resp["ts"],
            "thread": args.thread,
        }

    elif action == "edit":
        resp = client.chat_update(channel=args.channel, ts=args.message, text=args.text)
        return {"ok": True, "action": "edit", "messageId": resp["ts"]}

    elif action == "delete":
        resp = client.chat_delete(channel=args.channel, ts=args.message)
        return {"ok": True, "action": "delete", "messageId": args.message}

    elif action == "read":
        if args.thread:
            resp = client.conversations_replies(
                channel=args.channel, ts=args.thread, limit=args.limit
            )
        else:
            resp = client.conversations_history(channel=args.channel, limit=args.limit)
        messages = []
        for msg in resp.get("messages", []):
            messages.append({
                "user": msg.get("user", msg.get("bot_id", "unknown")),
                "text": msg.get("text", ""),
                "ts": msg["ts"],
                "thread_ts": msg.get("thread_ts"),
                "reply_count": msg.get("reply_count", 0),
            })
        return {"ok": True, "channel": args.channel, "messages": messages}

    elif action == "pin":
        resp = client.pins_add(channel=args.channel, timestamp=args.message)
        return {"ok": True, "action": "pin"}

    elif action == "unpin":
        resp = client.pins_remove(channel=args.channel, timestamp=args.message)
        return {"ok": True, "action": "unpin"}

    elif action == "pins":
        resp = client.pins_list(channel=args.channel)
        items = []
        for item in resp.get("items", []):
            msg = item.get("message", {})
            items.append({
                "text": msg.get("text", ""),
                "user": msg.get("user", ""),
                "ts": msg.get("ts", ""),
            })
        return {"ok": True, "pins": items}

    elif action == "member-info":
        resp = client.users_info(user=args.user)
        user = resp["user"]
        profile = user.get("profile", {})
        return {
            "ok": True,
            "user": {
                "id": user["id"],
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "display_name": profile.get("display_name"),
                "email": profile.get("email"),
                "title": profile.get("title"),
                "status_text": profile.get("status_text"),
                "status_emoji": profile.get("status_emoji"),
                "tz": user.get("tz"),
                "is_admin": user.get("is_admin", False),
                "is_bot": user.get("is_bot", False),
            },
        }

    elif action == "channels":
        resp = client.conversations_list(limit=args.limit, types="public_channel,private_channel")
        channels = []
        for ch in resp.get("channels", []):
            channels.append({
                "id": ch["id"],
                "name": ch.get("name"),
                "topic": ch.get("topic", {}).get("value", ""),
                "purpose": ch.get("purpose", {}).get("value", ""),
                "num_members": ch.get("num_members", 0),
                "is_private": ch.get("is_private", False),
            })
        return {"ok": True, "channels": channels}

    elif action == "search":
        resp = client.search_messages(query=args.query, count=args.limit)
        matches = resp.get("messages", {}).get("matches", [])
        results = []
        for m in matches:
            results.append({
                "text": m.get("text", ""),
                "user": m.get("user", m.get("username", "")),
                "channel": m.get("channel", {}).get("name", ""),
                "channel_id": m.get("channel", {}).get("id", ""),
                "ts": m.get("ts", ""),
                "permalink": m.get("permalink", ""),
            })
        return {"ok": True, "query": args.query, "results": results}

    elif action == "emoji-list":
        resp = client.emoji_list()
        return {"ok": True, "emoji": resp.get("emoji", {})}

    else:
        return {"ok": False, "error": f"Unknown action: {action}"}


if __name__ == "__main__":
    main()
