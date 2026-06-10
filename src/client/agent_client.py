"""
AI Agent Client — demonstrates the Agent Loop (ReAct) pattern.

Connects to the MCP server as a subprocess, discovers available tools,
and orchestrates a conversation loop between the user, an LLM, and
the MCP tools.

Usage:
    python -m src.client.agent_client

Requires:
    - OPENAI_API_KEY or ANTHROPIC_API_KEY set in environment / .env
    - LLM_PROVIDER set to "openai" or "anthropic"
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.config import Config, setup_logging

logger = setup_logging()

# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a helpful support ticket management assistant. You have access to tools 
for managing support tickets and searching a knowledge base.

Available tools:
- list_tickets: Query and filter existing tickets by status, priority, or category
- get_ticket: Get full details of a specific ticket (including comments)
- create_ticket: Create new support tickets
- add_comment: Add comments/notes to existing tickets
- search_kb: Search the knowledge base for solutions and documentation

When a user asks about support issues, follow this strategy:
1. First search the knowledge base for existing solutions
2. Check if a similar ticket already exists
3. Create new tickets only when necessary
4. Always provide helpful context from the KB when available
5. Be concise and actionable in your responses

When listing tickets, present them in a readable format.
When creating tickets, confirm what was created with the ticket ID.
"""


# ---------------------------------------------------------------------------
# LLM Client Abstraction
# ---------------------------------------------------------------------------


class LLMClient:
    """Abstraction over OpenAI and Anthropic APIs for the agent loop."""

    def __init__(self) -> None:
        self.provider = Config.LLM_PROVIDER
        self.model = Config.LLM_MODEL
        self._client: Any = None

    def initialize(self) -> None:
        """Initialize the LLM client based on the configured provider."""
        if self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info(f"LLM initialized: OpenAI {self.model}")
        elif self.provider == "gemini":
            from openai import OpenAI
            self._client = OpenAI(
                api_key=Config.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            logger.info(f"LLM initialized: Gemini (via OpenAI compat) {self.model}")
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            self._client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            logger.info(f"LLM initialized: Anthropic {self.model}")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Send a chat completion request to the LLM.

        Args:
            messages: Conversation history.
            tools: Available tool definitions in OpenAI function-calling format.

        Returns:
            Dict with 'content' (text) and/or 'tool_calls' (list of tool call dicts).
        """
        if self.provider in ("openai", "gemini"):
            return self._chat_openai(messages, tools)
        else:
            return self._chat_anthropic(messages, tools)

    def _chat_openai(
        self, messages: list[dict], tools: list[dict]
    ) -> dict[str, Any]:
        """Call OpenAI chat completions API."""
        # Convert MCP tool schemas to OpenAI function format
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"],
                },
            })

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        result: dict[str, Any] = {"content": msg.content or ""}

        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]

        return result

    def _chat_anthropic(
        self, messages: list[dict], tools: list[dict]
    ) -> dict[str, Any]:
        """Call Anthropic messages API."""
        # Convert MCP tool schemas to Anthropic tool format
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["inputSchema"],
            })

        # Separate system message from conversation
        system_msg = ""
        conv_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                conv_messages.append(msg)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_msg,
            messages=conv_messages,
            tools=anthropic_tools if anthropic_tools else None,
        )

        result: dict[str, Any] = {"content": ""}
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                result["content"] = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        if tool_calls:
            result["tool_calls"] = tool_calls

        return result


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------


async def agent_loop(
    session: ClientSession,
    llm: LLMClient,
    tools: list[dict[str, Any]],
    user_message: str,
) -> str:
    """
    Execute the ReAct (Reasoning + Acting) agent loop.

    1. Send user message + tool schemas to LLM
    2. If LLM returns tool calls → execute them via MCP → feed results back
    3. Repeat until LLM returns a text response (no tool calls)
    4. Return the final text response

    Args:
        session: Active MCP client session.
        llm: Initialized LLM client.
        tools: Tool definitions from the MCP server.
        user_message: The user's natural language request.

    Returns:
        The agent's final text response to the user.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(Config.MAX_AGENT_ITERATIONS):
        logger.info(f"Agent loop iteration {iteration + 1}/{Config.MAX_AGENT_ITERATIONS}")

        # Call LLM
        response = llm.chat(messages, tools)

        # Check if LLM wants to call tools
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # LLM returned a final text response
            return response.get("content", "I wasn't able to formulate a response.")

        # Execute each tool call via MCP
        if Config.LLM_PROVIDER in ("openai", "gemini"):
            # OpenAI format: append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            })
        else:
            # Anthropic: append assistant message
            content_blocks = []
            if response.get("content"):
                content_blocks.append({"type": "text", "text": response["content"]})
            for tc in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            messages.append({"role": "assistant", "content": content_blocks})

        for tc in tool_calls:
            logger.info(f"  → Calling tool: {tc['name']}({tc['arguments']})")

            # Execute tool via MCP client
            result = await session.call_tool(tc["name"], tc["arguments"])
            tool_result_text = ""
            if result.content:
                tool_result_text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

            logger.info(f"  ← Tool result: {tool_result_text[:200]}...")

            # Append tool result to conversation
            if Config.LLM_PROVIDER in ("openai", "gemini"):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result_text,
                })
            else:
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": tool_result_text,
                        }
                    ],
                })

    return (
        "I've reached the maximum number of reasoning steps. "
        "Here's what I found so far — please try a more specific query."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_agent() -> None:
    """Start the agent client, connect to MCP server, and enter the chat loop."""

    # Initialize LLM
    llm = LLMClient()
    issues = Config.validate()
    if issues:
        for issue in issues:
            logger.warning(f"Config warning: {issue}")

    try:
        llm.initialize()
    except Exception as e:
        print(f"\n❌ Failed to initialize LLM client: {e}")
        print("   Make sure your API key is set in .env or environment variables.")
        print("   See .env.example for configuration details.\n")
        return

    # Start MCP server as subprocess
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.server.mcp_server"],
    )

    print("\n" + "=" * 60)
    print("🎫  AI Ticket Management Assistant")
    print("=" * 60)
    print("Connected to MCP server. Type your requests in natural language.")
    print("Type 'quit' or 'exit' to end the session.")
    print("=" * 60 + "\n")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the MCP session
            await session.initialize()

            # Discover available tools
            tool_list = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in tool_list.tools
            ]
            logger.info(f"Discovered {len(tools)} MCP tools: {[t['name'] for t in tools]}")

            # Interactive chat loop
            while True:
                try:
                    user_input = input("\n👤 You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    break

                print("\n🤖 Assistant: ", end="", flush=True)
                try:
                    response = await agent_loop(session, llm, tools, user_input)
                    print(response)
                except Exception as e:
                    logger.exception("Agent loop error")
                    print(f"\n❌ Error: {e}")

    print("\n👋 Session ended. Goodbye!\n")


def main() -> None:
    """Entry point for the agent client."""
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
