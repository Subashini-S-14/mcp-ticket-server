"""
Custom Python Client for the AI Ticket Management MCP Server.

This script demonstrates how to connect to the MCP server natively using
the official Python MCP client SDK, discover tools, and call them
sequentially as required by the hackathon.

Run with:
    python client.py
"""

import asyncio
import json
import sys
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# We want the output to be clean and readable, so we'll set up some simple formatting
def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"🔹 {title}")
    print("=" * 60)

def print_result(result_text: str):
    """Attempt to pretty-print JSON responses from the server."""
    try:
        parsed = json.loads(result_text)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(result_text)

async def run_demo():
    print_header("Initializing MCP Client Connection")
    print("Launching MCP Server as a subprocess...")
    
    # Define the parameters to start the MCP server
    # We use the current Python executable to run our mcp_server module natively
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.server.mcp_server"],
    )

    # Establish the connection using the stdio_client context manager
    async with stdio_client(server_params) as (read, write):
        # Create a session over the stdio streams
        async with ClientSession(read, write) as session:
            
            # Step 0: Initialize and discover tools
            print("Sending initialization request...")
            await session.initialize()
            print("Connected successfully!")
            
            print_header("Available Tools")
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                print(f"🛠️ {tool.name}")
                print(f"   {tool.description[:80]}...")
            print()

            # Step 1: Create a ticket
            print_header("Step 1: Create a Ticket")
            create_args = {
                "title": "Login page returns 500 error",
                "description": "Users receive HTTP 500 after login",
                "priority": "high",
                "created_by": "demo_script"
            }
            print(f"Calling create_ticket with arguments:\n{json.dumps(create_args, indent=2)}\n")
            
            try:
                result = await session.call_tool("create_ticket", create_args)
                result_text = result.content[0].text if result.content else ""
                print_result(result_text)
                
                # Extract the generated ticket ID to use in subsequent steps
                parsed_res = json.loads(result_text)
                ticket_id = parsed_res["ticket"]["id"]
            except Exception as e:
                print(f"❌ Error creating ticket: {e}")
                return

            # Step 2: List all tickets
            print_header("Step 2: List All Tickets")
            print("Calling list_tickets (no arguments)...\n")
            try:
                result = await session.call_tool("list_tickets", {})
                result_text = result.content[0].text if result.content else ""
                print_result(result_text)
            except Exception as e:
                print(f"❌ Error listing tickets: {e}")

            # Step 3: Get the created ticket details
            print_header(f"Step 3: Get Ticket Details ({ticket_id})")
            print(f"Calling get_ticket for {ticket_id}...\n")
            try:
                result = await session.call_tool("get_ticket", {"ticket_id": ticket_id})
                result_text = result.content[0].text if result.content else ""
                print_result(result_text)
            except Exception as e:
                print(f"❌ Error getting ticket: {e}")

            # Step 4: Add a comment
            print_header(f"Step 4: Add a Comment to {ticket_id}")
            comment_args = {
                "ticket_id": ticket_id,
                "author": "demo_script",
                "content": "Investigating the issue"
            }
            print(f"Calling add_comment with arguments:\n{json.dumps(comment_args, indent=2)}\n")
            try:
                result = await session.call_tool("add_comment", comment_args)
                result_text = result.content[0].text if result.content else ""
                print_result(result_text)
            except Exception as e:
                print(f"❌ Error adding comment: {e}")

            # Step 5: Search KB
            print_header("Step 5: Search Knowledge Base")
            search_args = {
                "query": "login error"
            }
            print(f"Calling search_kb with arguments:\n{json.dumps(search_args, indent=2)}\n")
            try:
                result = await session.call_tool("search_kb", search_args)
                result_text = result.content[0].text if result.content else ""
                print_result(result_text)
            except Exception as e:
                print(f"❌ Error searching KB: {e}")

            print_header("Demo Completed Successfully! 🎉")

if __name__ == "__main__":
    try:
        # Suppress verbose debug logs from external libraries to keep output clean
        logging.basicConfig(level=logging.WARNING)
        
        # Windows requires ProactorEventLoop to work properly with subprocesses via stdio
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nFatal error: {e}")