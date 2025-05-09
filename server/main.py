from git import Repo
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import os
import requests
import base64

mcp = FastMCP("nlp-final-project")

@mcp.tool()
def clone_github_repo(repo_url: str) -> str:
    """Clone a repository from GitHub"""
    project_name = repo_url.rstrip('/').split('/')[-1]
    if project_name.endswith('.git'):
        project_name = project_name[:-4]
    
    clone_dir = project_name
    print(f"Project name detected: {project_name}")
    print(f"Cloning repository from {repo_url} to {clone_dir}...")
    
    try:
        Repo.clone_from(repo_url, f"repos/{clone_dir}")
        print("Clone successful!")
        return f"Successfully cloned {repo_url} to repos/{clone_dir}"
    except Exception as e:
        error_msg = f"Error cloning repository: {e}"
        print(error_msg)
        return error_msg

@mcp.tool()
def get_file_structure(file_path: str) -> str:
    """Get the file structure of a directory""" 
    def list_files(path):
        result = []
        try:
            for item in sorted(os.listdir(path)):
                startswith_excluded_patterns = ['.']
                endswith_excluded_patterns = ['.ipynb', '.jpg', '.png', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp', '.svg', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.lock']
                if any(item.startswith(p) for p in startswith_excluded_patterns) or any(item.endswith(p) for p in endswith_excluded_patterns):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    result.extend(list_files(item_path) or [])
                else:
                    result.append(f"  {path[6:]}/{item}")
            return result
        except Exception as e:
            return [f"Error accessing directory: {str(e)}"]
            
    files = list_files(f"repos/{file_path}")
    if not files:
        return "No files found or directory is empty"
    return "\n".join(files)

@mcp.tool()
def get_repo_list() -> str:
    """Get the list of repositories"""
    return "\n".join([f"  {dir}" for dir in os.listdir("repos")])

@mcp.tool()
def read_file(file_path: str) -> str:
    """Read a file"""
    with open(f"repos/{file_path}", "r") as file:
        return file.read()

@mcp.tool()
def search_github_repos(query: str) -> str:
    """Search for repositories on GitHub and return their metadata (without README)"""
    url = 'https://api.github.com/search/repositories'
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer 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', # You can change this to your own token
        'X-GitHub-Api-Version': '2022-11-28'
    }
    params = {'q': query}
    response = requests.get(url, params=params, headers=headers)
    result = []
    if response.status_code == 200:
        data = response.json()
        result.append(f"Total repositories found: {data['total_count']}\n")
        for repo in data['items']:
            result.append(f"Name: {repo['name']}")
            result.append(f"URL: {repo['html_url']}")
            result.append(f"Description: {repo['description']}")
            result.append(f"Stars: {repo['stargazers_count']}")
            result.append(f"Full Name: {repo['full_name']}")
            result.append("-" * 80 + "\n")
    else:
        result.append(f"Error: {response.status_code}")
        result.append(response.text)
    return "\n".join(result)

@mcp.tool()
def get_github_readme(full_name: str) -> str:
    """Fetch the README content for a given GitHub repository full_name (e.g., 'owner/repo')"""
    url = f"https://api.github.com/repos/{full_name}/readme"
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer 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', # You can change this to your own token
        'X-GitHub-Api-Version': '2022-11-28'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        readme_data = response.json()
        readme_content = base64.b64decode(readme_data['content']).decode('utf-8')
        return readme_content
    else:
        return f"README not found or inaccessible for {full_name} (status code: {response.status_code})"

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    mcp_server = mcp._mcp_server

    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)