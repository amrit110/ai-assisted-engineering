"""Example script to demonstrate the GitHub MCP server functionality using stdio mode."""

#!/usr/bin/env python3

import argparse
import base64
import json
import subprocess
import uuid
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table


# Initialize rich console
console = Console()


def header(text: str) -> None:
    """Display a header with nice formatting."""
    console.print(Panel(f"[bold blue]{text}[/]", border_style="blue"))


def run_mcp_command(
    method: str,
    params: Optional[dict[str, str]] = None,
    show_request: bool = False,
    show_raw_response: bool = False,
) -> Optional[list[dict[str, str]]]:
    """Run command directly against the MCP server via stdio."""
    request = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method}

    if params:
        request["params"] = params

    # Create command to pipe JSON to the container's stdin
    request_json = json.dumps(request)
    cmd = f"echo '{request_json}' | docker exec -i github-mcp-server ./github-mcp-server stdio"

    if show_request:
        console.print("[bold cyan]Request:[/]")
        syntax = Syntax(
            json.dumps(request, indent=2), "json", theme="monokai", line_numbers=False
        )
        console.print(syntax)

    # Execute the command with a spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]Executing request..."),
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=False
        )

    if result.returncode == 0:
        # Parse the JSON response
        output = result.stdout.strip()

        if show_raw_response:
            console.print("[bold yellow]Raw Response (truncated):[/]")
            truncated = output[:500] + "..." if len(output) > 500 else output
            console.print(truncated)

        try:
            # The response may have multiple JSON objects, each on its own line
            responses = []
            for line in output.split("\n"):
                if line.strip():
                    try:
                        responses.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        if show_raw_response:
                            console.print("[red]Failed to parse line[/]")

            return responses
        except Exception as e:
            console.print(f"[bold red]Error parsing response:[/] {str(e)}")
            return None
    else:
        console.print(
            f"[bold red]Command failed with return code {result.returncode}[/]"
        )
        console.print(f"[red]Error:[/] {result.stderr}")
        return None


def display_tools(tools, max_tools=30):
    """Display available tools in a table."""
    table = Table(
        title="GitHub MCP Server Tools", show_header=True, header_style="bold magenta"
    )
    table.add_column("Tool", style="cyan")
    table.add_column("Description")

    # Categorize and sort tools
    repo_tools = []
    file_tools = []
    other_tools = []

    for tool in tools:
        name = tool["name"].lower()
        if "repo" in name or "pull" in name or "issue" in name:
            repo_tools.append(tool)
        elif "file" in name or "content" in name:
            file_tools.append(tool)
        else:
            other_tools.append(tool)

    # Add most relevant tools first
    display_tools = (
        sorted(repo_tools, key=lambda x: x["name"])
        + sorted(file_tools, key=lambda x: x["name"])
        + sorted(other_tools, key=lambda x: x["name"])
    )

    # Add tools to the table (limited to max_tools)
    for tool in display_tools[:max_tools]:
        table.add_row(tool["name"], tool.get("description", "No description"))

    # Show a message about more tools if needed
    if len(tools) > max_tools:
        table.caption = f"Showing {max_tools} of {len(tools)} tools"

    console.print(table)


def display_repo(repo, index=1):
    """Display a GitHub repository with nice formatting."""
    panel = Panel(
        f"[bold cyan]{repo.get('full_name', 'Unknown')}[/]\n\n"
        f"[yellow]★ {repo.get('stargazers_count', 0):,}[/]   "
        f"[blue]◴ {repo.get('forks_count', 0):,}[/]   "
        f"({repo.get('language', 'Unknown')})\n\n"
        f"{repo.get('description', 'No description')}\n\n"
        f"[link={repo.get('html_url', '#')}]{repo.get('html_url', 'No URL')}[/link]",
        title=f"Repository {index}",
        border_style="green",
    )
    console.print(panel)


def extract_repos_from_response(response_data):
    """Extract repository data from complex JSON response structure."""
    # Check different response formats
    if isinstance(response_data, list):
        # Check if each item looks like a repository
        if all(
            isinstance(item, dict) and "full_name" in item for item in response_data[:3]
        ):
            return response_data

    elif isinstance(response_data, dict):
        # Format 1: Direct items field
        if "items" in response_data and isinstance(response_data["items"], list):
            return response_data["items"]

        # Format 2: Repositories field
        if "repositories" in response_data and isinstance(
            response_data["repositories"], list
        ):
            return response_data["repositories"]

        # Format 3: Content array with text items
        if "content" in response_data and isinstance(response_data["content"], list):
            for item in response_data["content"]:
                if isinstance(item, dict) and "text" in item:
                    try:
                        # Try to parse the text field as JSON
                        data = json.loads(item["text"])

                        # Check for repositories in various formats
                        if isinstance(data, dict):
                            if "items" in data and isinstance(data["items"], list):
                                return data["items"]
                            if "repositories" in data and isinstance(
                                data["repositories"], list
                            ):
                                return data["repositories"]
                            if "data" in data and isinstance(data["data"], list):
                                return data["data"]
                        elif isinstance(data, list):
                            if all(
                                isinstance(repo, dict) and "full_name" in repo
                                for repo in data[:3]
                            ):
                                return data
                    except:
                        pass

        # Format 4: Data field
        elif "data" in response_data and isinstance(response_data["data"], list):
            return response_data["data"]

    # If we couldn't extract repositories, return empty list
    return []


def get_tools_list(show_request=False):
    """Get list of available tools from the MCP server."""
    tools_result = run_mcp_command("tools/list", show_request=show_request)

    if not tools_result:
        console.print("[bold red]Failed to retrieve tools list.[/]")
        return None

    valid_result = next(
        (r for r in tools_result if "result" in r and "tools" in r["result"]), None
    )
    if not valid_result:
        console.print("[bold red]Invalid tools list response.[/]")
        return None

    return valid_result["result"]["tools"]


def display_available_tools():
    """Demonstrate listing available tools."""
    header("GitHub MCP Server Tools")

    console.print("\n[bold]Fetching available GitHub tools...[/]")
    tools_list = get_tools_list()

    if tools_list:
        display_tools(tools_list)


def search_popular_repos():
    """Search for popular GitHub repositories through MCP."""
    header("Popular GitHub Repositories")

    # Find the search repositories tool
    tools_list = get_tools_list(show_request=False)

    if not tools_list:
        return

    search_tool = next(
        (t for t in tools_list if t["name"] == "search_repositories"), None
    )

    if not search_tool:
        console.print("[bold red]search_repositories tool not found[/]")
        return

    # Search for popular repositories
    console.print("\n[bold]Searching for popular repositories...[/]")

    search_result = run_mcp_command(
        "tools/call",
        {
            "name": "search_repositories",
            "arguments": {"query": "stars:>10000", "perPage": 3},
        },
        show_raw_response=True,
    )

    # Extract repositories from the response
    if search_result:
        valid_search = next((r for r in search_result if "result" in r), None)

        if valid_search and "result" in valid_search:
            # Try to extract repositories list
            items_json = extract_repos_from_response(valid_search["result"])

            if items_json:
                console.print(
                    f"\n[bold green]Found {len(items_json)} popular repositories[/]"
                )
                for i, repo in enumerate(items_json[:3]):
                    display_repo(repo, i + 1)
            else:
                console.print(
                    "[bold yellow]No repositories extracted from the response[/]"
                )
        else:
            console.print("[bold red]Invalid search result response[/]")
    else:
        console.print("[bold red]Failed to search repositories[/]")


def get_readme_content():
    """Get README from a repository through MCP."""
    header("Repository README Example")

    # Find the file contents tool
    tools_list = get_tools_list(show_request=False)

    if not tools_list:
        return

    file_tool = next((t for t in tools_list if t["name"] == "get_file_contents"), None)

    if not file_tool:
        console.print("[bold red]get_file_contents tool not found[/]")
        return

    # Get README content
    console.print("\n[bold]Fetching README from a popular repository...[/]")

    file_result = run_mcp_command(
        "tools/call",
        {
            "name": "get_file_contents",
            "arguments": {"owner": "facebook", "repo": "react", "path": "README.md"},
        },
        show_raw_response=True,
    )

    # Extract and display README content
    if file_result:
        valid_file = next((r for r in file_result if "result" in r), None)

        if valid_file and "result" in valid_file:
            result = valid_file["result"]
            decoded_content = None

            # Using a direct approach first: extract the content directly using regex
            if (
                isinstance(result, dict)
                and "content" in result
                and isinstance(result["content"], list)
            ):
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        try:
                            raw_text = item["text"]

                            # Try to extract pattern from text: {"content":"BASE64DATA"}
                            import re

                            content_match = re.search(
                                r'"content"\s*:\s*"([^"]+)"', raw_text
                            )

                            if content_match:
                                base64_data = content_match.group(1)
                                # Replace escaped newlines
                                base64_data = base64_data.replace("\\n", "")
                                try:
                                    # Try to decode base64 content
                                    decoded_content = base64.b64decode(
                                        base64_data
                                    ).decode("utf-8")
                                    console.print(
                                        "[dim]Successfully extracted README content using regex[/]"
                                    )
                                    break
                                except Exception as e:
                                    console.print(
                                        f"[dim]Base64 decode error: {str(e)[:100]}[/]"
                                    )
                        except Exception as e:
                            console.print(
                                f"[dim]Regex extraction error: {str(e)[:100]}[/]"
                            )

            # If regex approach failed, try the previous approaches
            if not decoded_content:
                console.print(
                    "[dim]Regex approach failed for README, trying JSON parsing methods...[/]"
                )

                # Format 1: Direct content in result
                if isinstance(result, dict) and "content" in result:
                    try:
                        if isinstance(result["content"], str):
                            # Try to decode base64 content
                            decoded_content = base64.b64decode(
                                result["content"]
                            ).decode("utf-8")
                    except Exception as e:
                        console.print(f"[dim]Format 1 extraction failed: {e}[/]")

                # Format 2: Result is a list of content items with text field
                elif isinstance(result, list) and len(result) > 0:
                    for item in result:
                        if isinstance(item, dict) and "text" in item:
                            try:
                                text = (
                                    item["text"]
                                    .replace("\n", "")
                                    .replace("\\n", "")
                                    .strip()
                                )
                                content_json = json.loads(text)

                                if (
                                    isinstance(content_json, dict)
                                    and "content" in content_json
                                ):
                                    # Try to decode the base64 content
                                    decoded_content = base64.b64decode(
                                        content_json["content"]
                                    ).decode("utf-8")
                                    break
                            except Exception as e:
                                console.print(
                                    f"[dim]README parsing error: {str(e)[:100]}[/]"
                                )

                # Format 3: Content array in result
                elif (
                    isinstance(result, dict)
                    and "content" in result
                    and isinstance(result["content"], list)
                ):
                    for item in result["content"]:
                        if isinstance(item, dict) and "text" in item:
                            try:
                                # Try to parse the text field
                                text = (
                                    item["text"]
                                    .replace("\n", "")
                                    .replace("\\n", "")
                                    .strip()
                                )
                                content_json = json.loads(text)

                                if (
                                    isinstance(content_json, dict)
                                    and "content" in content_json
                                ):
                                    # Try to decode the base64 content
                                    decoded_content = base64.b64decode(
                                        content_json["content"]
                                    ).decode("utf-8")
                                    break
                                if isinstance(content_json, str):
                                    # Maybe the content is directly in text
                                    decoded_content = content_json
                                    break
                            except Exception as e:
                                console.print(
                                    f"[dim]README format 3 parsing error: {str(e)[:100]}[/]"
                                )
                                # Maybe the text is directly the content
                                if "text" in item and isinstance(item["text"], str):
                                    # Check if it looks like markdown
                                    if "# " in item["text"] or "## " in item["text"]:
                                        decoded_content = item["text"]
                                        break

            # Display the content if found
            if decoded_content:
                # Display the first part of the content
                preview = (
                    decoded_content[:800] + "..."
                    if len(decoded_content) > 800
                    else decoded_content
                )
                console.print("[bold green]README.md from facebook/react:[/]")
                console.print(
                    Panel(preview, border_style="green", title="README.md Preview")
                )
            else:
                console.print(
                    "[bold yellow]Could not extract README content from response[/]"
                )
                console.print("[dim]Response structure (truncated):[/]")
                console.print(json.dumps(result, indent=2)[:300] + "...")
        else:
            console.print("[bold red]Invalid file result response[/]")
    else:
        console.print("[bold red]Failed to fetch README[/]")


def list_org_repos():
    """List repositories from a GitHub organization through MCP."""
    # Define the organization to query
    org_name = "VectorInstitute"

    header(f"{org_name} GitHub Repositories")

    # Find the required tools
    tools_list = get_tools_list(show_request=False)

    if not tools_list:
        return

    # Try to use search for organization repositories
    search_tool = next(
        (t for t in tools_list if t["name"] == "search_repositories"), None
    )

    if not search_tool:
        console.print("[bold red]search_repositories tool not found[/]")
        return

    console.print(f"\n[bold]Listing repositories for organization: {org_name}...[/]")

    # Search for repositories in the organization
    repos_result = run_mcp_command(
        "tools/call",
        {
            "name": "search_repositories",
            "arguments": {
                "query": f"org:{org_name}",
                "perPage": 5,  # Show more repos from the organization
            },
        },
        show_raw_response=True,
    )

    # Process search result
    if repos_result:
        valid_repos = next((r for r in repos_result if "result" in r), None)

        if valid_repos and "result" in valid_repos:
            # Try to extract repositories from the result
            repos_json = extract_repos_from_response(valid_repos["result"])

            if repos_json and len(repos_json) > 0:
                console.print(
                    f"\n[bold green]Found {len(repos_json)} repositories for {org_name}[/]"
                )
                for i, repo in enumerate(repos_json[:5]):
                    display_repo(repo, i + 1)
            else:
                console.print(f"[bold yellow]No repositories found for {org_name}[/]")

                # Fallback: try alternative query format
                console.print("[dim]Trying alternative query format...[/]")

                alt_repos_result = run_mcp_command(
                    "tools/call",
                    {
                        "name": "search_repositories",
                        "arguments": {"query": f"user:{org_name}", "perPage": 5},
                    },
                    show_raw_response=False,
                )

                if alt_repos_result:
                    alt_valid_repos = next(
                        (r for r in alt_repos_result if "result" in r), None
                    )

                    if alt_valid_repos and "result" in alt_valid_repos:
                        alt_repos_json = extract_repos_from_response(
                            alt_valid_repos["result"]
                        )

                        if alt_repos_json and len(alt_repos_json) > 0:
                            console.print(
                                f"\n[bold green]Found {len(alt_repos_json)} repositories for {org_name} using alternative query[/]"
                            )
                            for i, repo in enumerate(alt_repos_json[:5]):
                                display_repo(repo, i + 1)
                        else:
                            console.print(
                                f"[bold yellow]No repositories found for {org_name} with alternative query[/]"
                            )
        else:
            console.print("[bold red]Invalid repositories response[/]")
    else:
        console.print("[bold red]Failed to retrieve repositories[/]")


def get_specific_file(owner, repo, file_path):
    """Fetch a specific file from a repository and print its contents."""
    header(f"Fetching {file_path} from {owner}/{repo}")

    # Find the file contents tool
    tools_list = get_tools_list(show_request=False)

    if not tools_list:
        return None

    file_tool = next((t for t in tools_list if t["name"] == "get_file_contents"), None)

    if not file_tool:
        console.print("[bold red]get_file_contents tool not found[/]")
        return None

    console.print(f"\n[bold]Fetching {file_path} from {owner}/{repo}...[/]")

    return run_mcp_command(
        "tools/call",
        {
            "name": "get_file_contents",
            "arguments": {"owner": owner, "repo": repo, "path": file_path},
        },
        show_raw_response=True,
    )


def extract_file_content(file_result):
    """Extract content from a file result response."""
    if not file_result:
        console.print("[bold red]Failed to fetch file[/]")
        return None

    valid_file = next((r for r in file_result if "result" in r), None)

    if not valid_file or "result" not in valid_file:
        console.print("[bold red]Invalid file result response[/]")
        return None

    result = valid_file["result"]
    file_content = None

    # For debugging the actual response
    raw_result = json.dumps(result, indent=2)[:300]
    console.print(f"[dim]Debug raw result: {raw_result}...[/]")

    # Using a direct approach first: extract the content directly from the text field
    if (
        isinstance(result, dict)
        and "content" in result
        and isinstance(result["content"], list)
    ):
        for item in result["content"]:
            if isinstance(item, dict) and "text" in item:
                try:
                    # The issue might be the escaped newlines in the base64 content
                    raw_text = item["text"]

                    # Try to extract pattern from text: {"content":"BASE64DATA"}
                    import re

                    content_match = re.search(r'"content"\s*:\s*"([^"]+)"', raw_text)

                    if content_match:
                        base64_data = content_match.group(1)
                        # Replace escaped newlines
                        base64_data = base64_data.replace("\\n", "")
                        try:
                            # Try to decode base64 content
                            file_content = base64.b64decode(base64_data).decode("utf-8")
                            console.print(
                                "[dim]Successfully extracted content using regex[/]"
                            )
                            break
                        except Exception as e:
                            console.print(
                                f"[dim]Base64 decode error: {str(e)[:100]}[/]"
                            )
                except Exception as e:
                    console.print(f"[dim]Regex extraction error: {str(e)[:100]}[/]")

    # If the regex approach failed, try the previous approaches
    if not file_content:
        console.print("[dim]Regex approach failed, trying JSON parsing methods...[/]")

        # Try various response formats to extract file content
        # Format 1: Direct content in result
        if isinstance(result, dict) and "content" in result:
            try:
                if isinstance(result["content"], str):
                    # Try to decode base64 content
                    file_content = base64.b64decode(result["content"]).decode("utf-8")
            except Exception as e:
                console.print(f"[dim]Format 1 extraction failed: {e}[/]")

        # Format 2: Result is a list of content items with text field
        elif isinstance(result, list) and len(result) > 0:
            for item in result:
                if isinstance(item, dict) and "text" in item:
                    try:
                        text = item["text"].replace("\n", "").replace("\\n", "").strip()
                        content_json = json.loads(text)

                        if isinstance(content_json, dict) and "content" in content_json:
                            # Try to decode base64 content
                            file_content = base64.b64decode(
                                content_json["content"]
                            ).decode("utf-8")
                            break
                    except Exception as e:
                        console.print(f"[dim]JSON parsing error: {str(e)[:100]}[/]")
                        # Maybe the text is directly the content (not base64 encoded)
                        if isinstance(item["text"], str) and (
                            item["text"].startswith("{") or item["text"].startswith("[")
                        ):
                            try:
                                # If it's JSON, format it nicely
                                file_content = json.dumps(
                                    json.loads(item["text"]), indent=2
                                )
                                break
                            except json.JSONDecodeError as e:
                                file_content = item["text"]
                                break

    if not file_content:
        console.print("[bold yellow]Could not extract file content from response[/]")
        console.print("[dim]Response structure (truncated):[/]")
        console.print(json.dumps(result, indent=2)[:300] + "...")

    return file_content


def display_file_content(file_path, owner, repo, file_content):
    """Display file content with appropriate formatting."""
    if not file_content:
        return

    # Determine the language for syntax highlighting
    language = "json" if file_path.endswith(".json") else "text"
    if file_path.endswith(".js"):
        language = "javascript"
    elif file_path.endswith(".py"):
        language = "python"
    elif file_path.endswith(".md"):
        language = "markdown"
    elif file_path.endswith(".rst"):
        language = "rst"

    # Set a reasonable display limit to avoid overwhelming the console
    preview_length = 2000
    preview = (
        file_content[:preview_length] + "..."
        if len(file_content) > preview_length
        else file_content
    )

    console.print(f"[bold green]Contents of {file_path} from {owner}/{repo}:[/]")

    # Use syntax highlighting if possible
    syntax = Syntax(preview, language, theme="monokai", line_numbers=True)
    console.print(syntax)

    console.print(f"[dim]File size: {len(file_content)} characters[/]")


def fetch_specific_repo_file():
    """Fetch a specific file from a Vector Institute repository."""
    file_result = get_specific_file("VectorInstitute", "vector-inference", "README.md")
    file_content = extract_file_content(file_result)
    if file_content:
        display_file_content(
            "README.md", "VectorInstitute", "vector-inference", file_content
        )


def read_api_docs():
    """Find and display API documentation from a repository."""
    header("Repository API Documentation")

    # Select a repository from VectorInstitute that likely has API documentation
    owner = "VectorInstitute"
    repo = "health-rec"

    # First, check if the repository has common API documentation locations
    possible_doc_paths = [
        "docs/api.md",
        "docs/API.md",
        "docs/api/README.md",
        "docs/index.md",
        "docs/api/index.md",
        "docs/README.md",
        "docs/usage.md",
        "API.md",
        "api.md",
    ]

    # Try to find which API doc file exists
    console.print(f"\n[bold]Searching for API documentation in {owner}/{repo}...[/]")

    # Let's first check if a docs directory exists
    docs_result = get_specific_file(owner, repo, "docs")

    if docs_result:
        valid_file = next((r for r in docs_result if "result" in r), None)
        if valid_file and "result" in valid_file and "message" not in valid_file:
            console.print(
                "[bold green]Found docs directory. Looking for API documentation files...[/]"
            )
        else:
            # If docs directory doesn't exist, try common files at root
            console.print(
                "[dim]No docs directory found. Looking for API documentation at repository root...[/]"
            )
            possible_doc_paths = [
                "API.md",
                "api.md",
                "USAGE.md",
                "usage.md",
                "README.md",
            ]

    # Search for API documentation files
    api_doc_content = None
    api_doc_path = None

    for path in possible_doc_paths:
        console.print(f"[dim]Checking {path}...[/]")
        file_result = get_specific_file(owner, repo, path)

        if file_result:
            valid_file = next(
                (r for r in file_result if "result" in r and "message" not in r), None
            )
            if valid_file and "result" in valid_file:
                api_doc_content = extract_file_content(file_result)
                if api_doc_content:
                    api_doc_path = path
                    console.print(f"[bold green]Found API documentation at {path}[/]")
                    break

    # As a fallback, if we didn't find any of the common files, look for README.md
    # in root or docs directory
    if not api_doc_content:
        console.print(
            "[dim]No specific API documentation found. Trying README.md...[/]"
        )
        readme_result = get_specific_file(owner, repo, "README.md")

        if readme_result:
            api_doc_content = extract_file_content(readme_result)
            if api_doc_content:
                api_doc_path = "README.md"
                console.print(
                    "[bold green]Using README.md as it may contain API information[/]"
                )

    # Display the API documentation if found
    if api_doc_content:
        display_file_content(api_doc_path, owner, repo, api_doc_content)

        # Check if the content actually has API documentation
        api_keywords = [
            "api",
            "function",
            "method",
            "class",
            "parameter",
            "usage",
            "example",
        ]
        has_api_content = any(
            keyword in api_doc_content.lower() for keyword in api_keywords
        )

        if not has_api_content:
            console.print(
                "[bold yellow]Note: This file might not contain detailed API documentation.[/]"
            )

            # Try to find a Python example file as another approach
            console.print("[dim]Looking for Python example files...[/]")
            example_paths = [
                "examples/example.py",
                "example.py",
                "examples/demo.py",
                "demo.py",
            ]

            for path in example_paths:
                example_result = get_specific_file(owner, repo, path)
                if example_result:
                    example_content = extract_file_content(example_result)
                    if example_content:
                        console.print(
                            "[bold green]Found an example file that might help with API usage:[/]"
                        )
                        display_file_content(path, owner, repo, example_content)
                        break
    else:
        console.print(
            "[bold red]Could not find API documentation for this repository.[/]"
        )

        # As a last resort, try to find a Python file that might show API usage
        console.print(
            "[dim]Trying to find a Python source file that might demonstrate API usage...[/]"
        )
        source_paths = [
            "src/main.py",
            "src/__init__.py",
            "cyclops/__init__.py",
            "main.py",
        ]

        for path in source_paths:
            source_result = get_specific_file(owner, repo, path)
            if source_result:
                source_content = extract_file_content(source_result)
                if source_content:
                    console.print(
                        "[bold green]Found a source file that might help understand the API:[/]"
                    )
                    display_file_content(path, owner, repo, source_content)
                    break


def run_all_demos():
    """Run all demo functions."""
    header("GitHub MCP Server in Stdio Mode - Full Demo")

    # Get list of tools
    console.print("\n[bold]Fetching available GitHub tools...[/]")
    tools_list = get_tools_list(show_request=False)

    # Process tools
    if not tools_list:
        console.print("[bold red]Failed to retrieve tools list.[/]")
        return

    # Display tools
    display_tools(tools_list)

    # Search for popular repositories
    search_popular_repos()

    # Get README content
    get_readme_content()

    # List organization repositories
    list_org_repos()

    # Get specific file from repository
    fetch_specific_repo_file()

    # Find and display API documentation
    read_api_docs()

    console.print("\n[bold green]Demo completed successfully![/]")


def list_available_demos():
    """List all available demos with descriptions."""
    header("Available GitHub MCP Demos")

    table = Table(title="Demo Options", show_header=True, header_style="bold magenta")
    table.add_column("Flag", style="cyan")
    table.add_column("Description")

    demos = [
        ("--list_demos", "List all available demos"),
        ("--display_tools", "Show available GitHub MCP tools"),
        ("--search_repos", "Search for popular GitHub repositories"),
        ("--get_readme", "Fetch and display README from a repository"),
        ("--list_org_repos", "List repositories from a specific organization"),
        ("--get_repo_file", "Fetch a specific file from a repository"),
        ("--get_api_docs", "Find and display API documentation"),
        ("--run_all", "Run all demos in sequence"),
    ]

    for demo in demos:
        table.add_row(demo[0], demo[1])

    console.print(table)
    console.print(
        "\n[bold]Example usage:[/] python github_mcp_example.py --search_repos"
    )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="GitHub MCP Server Demo")

    # Add a flag for each demo function
    parser.add_argument(
        "--list_demos", action="store_true", help="List all available demos"
    )
    parser.add_argument(
        "--display_tools", action="store_true", help="Show available GitHub MCP tools"
    )
    parser.add_argument(
        "--search_repos",
        action="store_true",
        help="Search for popular GitHub repositories",
    )
    parser.add_argument(
        "--get_readme",
        action="store_true",
        help="Fetch and display README from a repository",
    )
    parser.add_argument(
        "--list_org_repos",
        action="store_true",
        help="List repositories from a specific organization",
    )
    parser.add_argument(
        "--get_repo_file",
        action="store_true",
        help="Fetch a specific file from a repository",
    )
    parser.add_argument(
        "--get_api_docs", action="store_true", help="Find and display API documentation"
    )
    parser.add_argument(
        "--run_all", action="store_true", help="Run all demos in sequence"
    )

    return parser.parse_args()


def main():
    """Run main function to run the GitHub MCP server demo."""
    args = parse_arguments()

    # Check if any flag was specified
    any_flag_specified = any(
        [
            args.list_demos,
            args.display_tools,
            args.search_repos,
            args.get_readme,
            args.list_org_repos,
            args.get_repo_file,
            args.get_api_docs,
            args.run_all,
        ]
    )

    # If no flags specified, run all demos (default behavior)
    if not any_flag_specified:
        list_available_demos()
        console.print(
            "\n[bold yellow]No demo specified. Use one of the flags above to run a specific demo.[/]"
        )
        return

    # Run the demos based on the specified flags
    if args.list_demos:
        list_available_demos()

    if args.display_tools:
        display_available_tools()

    if args.search_repos:
        search_popular_repos()

    if args.get_readme:
        get_readme_content()

    if args.list_org_repos:
        list_org_repos()

    if args.get_repo_file:
        fetch_specific_repo_file()

    if args.get_api_docs:
        read_api_docs()

    if args.run_all:
        run_all_demos()


if __name__ == "__main__":
    main()
