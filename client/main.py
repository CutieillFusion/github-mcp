import asyncio
import os
import re
from typing import Optional, List, Dict
from contextlib import AsyncExitStack
from colorama import init, Fore, Style

from sshtunnel import SSHTunnelForwarder
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI
from dotenv import load_dotenv

init()

load_dotenv()

class MCPClient:
    def __init__(self, tunnel: SSHTunnelForwarder):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._session_context = None
        self._streams_context = None
        self.tunnel = tunnel
        self.openai_client = None
        self.chat_history: List[Dict[str, str]] = [
            {
                "role": "system", 
                "content": """
You are a helpful assistant that can use tools to help with coding tasks. Try to have concise responses. 
If you are asked a question about a codebase, try to use the commands to answer the question.
You can 0 to n number of repositories in your context.
Its recommended for youto use the /lr command to list the repositories in your context before using any other commands, only do this if a coding question is asked.

None of the commands support "*", ".", or "?". Only one path is supported at a time.

You can use the following commands:
/lr - List available repositories
/fs <path> - Gets file repository's structure
/ac <path> - Adds one file to context
/search <query> - Search GitHub repositories
/readme <owner/repo> - Get README for a GitHub repository
/clone <repo_url> - Clone a GitHub repository (make sure repo_url ends with .git)

Before performing a /fs command, always use the /lr command to see the available repositories. You are allowed to clone repositories to your context if its not already cloned.
When searching for a repository use the raw string instead of a formatted http parameter, spaces are allowed. The search query should be short and is found by if its similar to the repository name.
When left with a number of candidate repositories, instead of asking the user to choose, investigate each repository and return the best one.
When asked a task that will take multiple steps think about your thought process and return a command to execute the task. Any thought process should be returned in the response <thought>...</thought>.
If and only if you are returning a command return it exactly as you want it to be executed in the format <command>....</command>. If you return a invalid or multiple commands will error.
You can return multiple commands, and they will be processed in order.

If you are not returning a command, just return the response to the user."""
            }
        ]

    async def connect_to_sse_server(self, server_url: str):
        try:
            print(f"{Fore.LIGHTCYAN_EX}Attempting to connect to SSE server at {server_url}{Style.RESET_ALL}")
            
            self._streams_context = sse_client(url=server_url)
            print(f"{Fore.LIGHTCYAN_EX}Created SSE client context{Style.RESET_ALL}")
            
            streams = await self._streams_context.__aenter__()
            print(f"{Fore.LIGHTCYAN_EX}Entered SSE streams context{Style.RESET_ALL}")

            self._session_context = ClientSession(*streams)
            print(f"{Fore.LIGHTCYAN_EX}Created client session{Style.RESET_ALL}")
            
            self.session: ClientSession = await self._session_context.__aenter__()
            print(f"{Fore.LIGHTCYAN_EX}Entered client session context{Style.RESET_ALL}") 

            await self.session.initialize()
            print(f"{Fore.LIGHTCYAN_EX}Initialized SSE client successfully{Style.RESET_ALL}")

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print(f"{Fore.RED}Error: OPENAI_API_KEY not found in .env file{Style.RESET_ALL}")
                raise ValueError("OPENAI_API_KEY not found in environment variables")
                
            self.openai_client = OpenAI(api_key=api_key)
            print(f"{Fore.LIGHTCYAN_EX}Initialized OpenAI client successfully{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}Error during connection: {str(e)}{Style.RESET_ALL}")
            await self.cleanup()
            raise e

    async def cleanup(self):
        print(f"{Fore.LIGHTCYAN_EX}Cleaning up connections...{Style.RESET_ALL}")
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)
        print(f"{Fore.LIGHTCYAN_EX}Cleanup complete{Style.RESET_ALL}")

    async def add_context(self, file_path: str, user: bool = True) -> str:
        response = await self.session.call_tool("read_file", {"file_path": file_path})
        if not user:
            self.chat_history.append({"role": "system", "content": f"Adding file contents of {file_path} to context..."})
            self.chat_history.append({"role": "system", "content": response.content[0].text})
        print(f"{Fore.YELLOW}Added context from {file_path}{Style.RESET_ALL}")

    async def get_file_structure(self, file_path: str, user: bool = True):
        response = await self.session.call_tool("get_file_structure", {"file_path": file_path})
        if not user:
            self.chat_history.append({"role": "system", "content": f"Getting file structure of {file_path}..."})
            self.chat_history.append({"role": "system", "content": response.content[0].text})
        print(f"{Fore.YELLOW}File structure:{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{response.content[0].text}{Style.RESET_ALL}")

    async def get_repo_list(self, user: bool = True):
        response = await self.session.call_tool("get_repo_list")
        if not user:
            self.chat_history.append({"role": "system", "content": f"Getting list of repositories..."})
            self.chat_history.append({"role": "system", "content": response.content[0].text})
        print(f"{Fore.YELLOW}Repositories:{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{response.content[0].text}{Style.RESET_ALL}")

    async def search_github_repos(self, query: str, user: bool = True):
        response = await self.session.call_tool("search_github_repos", {"query": query})
        if not user:
            self.chat_history.append({"role": "system", "content": f"Searching GitHub repositories for '{query}'..."})
            self.chat_history.append({"role": "system", "content": response.content[0].text})
        print(f"{Fore.YELLOW}GitHub search results for '{query}':{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{response.content[0].text}{Style.RESET_ALL}")

    async def get_github_readme(self, full_name: str, user: bool = True):
        response = await self.session.call_tool("get_github_readme", {"full_name": full_name})
        if not user:
            self.chat_history.append({"role": "system", "content": f"Getting README for GitHub repository '{full_name}'..."})
            self.chat_history.append({"role": "system", "content": response.content[0].text})
        print(f"{Fore.YELLOW}README for GitHub repository '{full_name}':{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{response.content[0].text}{Style.RESET_ALL}")

    async def list_info(self):
        response = await self.session.list_tools()
        tools = response.tools
        print(f"{Fore.YELLOW}Tools:{Style.RESET_ALL}")
        print("\n".join([f"  {Fore.BLUE}{tool.name}{Style.RESET_ALL}: {tool.description}" for tool in tools]))
        
        response = await self.session.list_resources()
        resources = response.resources
        print(f"{Fore.YELLOW}Resources:{Style.RESET_ALL}")
        print("\n".join([f"  {Fore.BLUE}{resource.name}{Style.RESET_ALL}: {resource.uri}" for resource in resources]))

        response = await self.session.list_resource_templates()
        resource_templates = response.resourceTemplates
        print(f"{Fore.YELLOW}Resource templates:{Style.RESET_ALL}")
        print("\n".join([f"  {Fore.BLUE}{resource_template.name}{Style.RESET_ALL}: {resource_template.uriTemplate}" for resource_template in resource_templates]))

    async def clone_repo(self, repo_url: str):
        response = await self.session.call_tool("clone_github_repo", {"repo_url": repo_url})
        print(f"{Fore.YELLOW}Cloned repo: {response.content[0].text}{Style.RESET_ALL}")

    async def chat(self, query: Optional[str] = None, stream: bool = True):
        self.openai_client._client.headers["Accept"] = "text/event-stream" if stream else "application/json"

        if query:
            self.chat_history.append({"role": "user", "content": query})

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.chat_history,
            max_completion_tokens=2048,
            temperature=1.0,
            top_p=1.0,
            stream=stream
        )

        print(f"{Fore.BLUE}GPT:{Style.RESET_ALL}", end=" ")
        complete_response = ""
        if stream:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    complete_response += content
                    print(f"{Style.BRIGHT}{content}{Style.RESET_ALL}", end='', flush=True)
            print()
        else:
            complete_response = response.choices[0].message.content
            print(f"{Style.BRIGHT}{complete_response}{Style.RESET_ALL}")

        self.chat_history.append({"role": "assistant", "content": complete_response})

        while True:
            pattern = re.compile(r"<command>(.*?)</command>", re.DOTALL)
            matches = pattern.findall(complete_response)
            if not matches:
                break

            for command_text in matches:
                command = command_text.strip()
                self.chat_history.append({"role": "system", "content": f"Executing command: {command}"})
                if command.lower() == "/lr":
                    await self.get_repo_list(user=False)
                elif command.startswith("/clone "):
                    if command.endswith(".git"):
                        await self.clone_repo(command[7:])
                    else:
                        print(f"{Fore.RED}Error: Invalid repository URL{Style.RESET_ALL}")
                elif command.startswith("/fs "):
                    if len(command) > 4:
                        await self.get_file_structure(command[4:], user=False)
                    else:
                        print(f"{Fore.RED}Error: No path provided{Style.RESET_ALL}")
                elif command.startswith("/ac "):
                    if len(command) > 4:
                        await self.add_context(command[4:], user=False)
                    else:
                        print(f"{Fore.RED}Error: No path provided{Style.RESET_ALL}")
                elif command.startswith("/search "):
                    if len(command) > 8:
                        await self.search_github_repos(command[8:], user=False)
                    else:
                        print(f"{Fore.RED}Error: No search query provided{Style.RESET_ALL}")
                elif command.startswith("/readme "):
                    if len(command) > 8:
                        await self.get_github_readme(command[8:], user=False)
                    else:
                        print(f"{Fore.RED}Error: No repository name provided{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Error: Invalid command: {command}{Style.RESET_ALL}")
            
            complete_response = re.sub(r"<command>.*?</command>", "", complete_response, flags=re.DOTALL)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.chat_history,
                max_completion_tokens=2048,
                temperature=1.0,
                top_p=1.0,
                stream=stream
            )

            print(f"{Fore.BLUE}GPT:{Style.RESET_ALL}", end=" ")
            complete_response = ""
            if stream:
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        complete_response += content
                        print(f"{Style.BRIGHT}{content}{Style.RESET_ALL}", end='', flush=True)
                print()
            else:
                complete_response = response.choices[0].message.content
                print(f"{Style.BRIGHT}{complete_response}{Style.RESET_ALL}")

            self.chat_history.append({"role": "assistant", "content": complete_response})

    async def chat_loop(self):
        print(f"{Fore.GREEN}MCP Client Started!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Type your queries or '/quit' to exit.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Available commands:{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}/info{Style.RESET_ALL} - List available tools and resources")
        print(f"  {Fore.YELLOW}/lr{Style.RESET_ALL} - List available repositories")
        print(f"  {Fore.YELLOW}/clone <repo_url>{Style.RESET_ALL} - Clone a GitHub repository")
        print(f"  {Fore.YELLOW}/fs <path>{Style.RESET_ALL} - Get file structure")
        print(f"  {Fore.YELLOW}/ac <path>{Style.RESET_ALL} - Add a file for context")
        print(f"  {Fore.YELLOW}/search <query>{Style.RESET_ALL} - Search GitHub repositories")
        print(f"  {Fore.YELLOW}/readme <owner/repo>{Style.RESET_ALL} - Get README for a GitHub repository")
        print(f"  {Fore.YELLOW}/history{Style.RESET_ALL} - Show chat history") 
        print(f"  {Fore.YELLOW}/clear{Style.RESET_ALL} - Clear chat history")
        print(f"  {Fore.YELLOW}/stream{Style.RESET_ALL} - Toggle streaming mode")
        print(f"  {Fore.YELLOW}/quit{Style.RESET_ALL} - Exit the chat")

        stream = True
        while True:
            try:
                query = input(f"{Fore.GREEN}User:{Style.RESET_ALL} ").strip()
                if query.lower() == '/quit':
                    break
                elif query.lower() == '/history':
                    print(f"{Fore.YELLOW}Chat History:{Style.RESET_ALL}")
                    for msg in self.chat_history:
                        if msg['role'] == 'user':
                            print(f"{Fore.GREEN}User:{Style.RESET_ALL} {msg['content']}")
                        elif msg['role'] == 'assistant':
                            print(f"{Fore.BLUE}GPT:{Style.RESET_ALL} {msg['content']}")
                        else:
                            print(f"{Fore.LIGHTMAGENTA_EX}{msg['role'].title()}{Style.RESET_ALL}: {msg['content']}")
                    print()
                elif query.lower() == '/clear':
                    self.chat_history = [self.chat_history[0]]
                    print(f"{Fore.YELLOW}Chat history cleared.{Style.RESET_ALL}")
                elif query.lower() == '/stream':
                    stream = not stream
                    print(f"{Fore.YELLOW}Streaming {'enabled' if stream else 'disabled'}.{Style.RESET_ALL}")
                elif query.lower() == "/info":
                    await self.list_info()
                elif query.lower() == "/lr":
                    await self.get_repo_list()
                elif query.startswith("/clone "):
                    if query.endswith(".git"):
                        await self.clone_repo(query[7:])
                    else:
                        print(f"{Fore.RED}Error: Invalid repository URL{Style.RESET_ALL}")
                elif query.startswith("/fs "):
                    if len(query) > 4:
                        await self.get_file_structure(query[4:])
                    else:
                        print(f"{Fore.RED}Error: No path provided{Style.RESET_ALL}")
                elif query.startswith("/ac "):
                    if len(query) > 4:
                        await self.add_context(query[4:])
                    else:
                        print(f"{Fore.RED}Error: No path provided{Style.RESET_ALL}")
                elif query.startswith("/search "):
                    if len(query) > 8:
                        await self.search_github_repos(query[8:])
                    else:
                        print(f"{Fore.RED}Error: No search query provided{Style.RESET_ALL}")
                elif query.startswith("/readme "):
                    if len(query) > 8:
                        await self.get_github_readme(query[8:])
                    else:
                        print(f"{Fore.RED}Error: No repository name provided{Style.RESET_ALL}")
                else:
                    await self.chat(query, stream=stream)
            except Exception as e:
                print()
                print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")

async def main():
    try:
        print(f"{Fore.LIGHTCYAN_EX}Starting connection process...{Style.RESET_ALL}")
        
        hpc_host = os.getenv("HPC_HOST")
        hpc_username = os.getenv("HPC_USERNAME")
        hpc_password = os.getenv("HPC_PASSWORD")
        remote_port = int(os.getenv("HPC_SSE_PORT", "8080"))
        local_port = int(os.getenv("LOCAL_PORT", "8080"))
        sse_endpoint = os.getenv("SSE_ENDPOINT", "/sse")

        print(f"{Fore.LIGHTCYAN_EX}Connecting to HPC host: {hpc_host}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Username: {hpc_username}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Remote port: {remote_port}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Local port: {local_port}{Style.RESET_ALL}")

        with SSHTunnelForwarder(
            (hpc_host, 22),
            ssh_username=hpc_username,
            ssh_password=hpc_password,
            remote_bind_address=("127.0.0.1", remote_port),
            local_bind_address=("127.0.0.1", local_port)
        ) as sse_tunnel, SSHTunnelForwarder(
            (hpc_host, 22),
            ssh_username=hpc_username,
            ssh_password=hpc_password,
            remote_bind_address=(os.getenv("MODEL_HOST"), int(os.getenv("MODEL_PORT"))),
            local_bind_address=("127.0.0.1", local_port + 1)
        ) as chat_tunnel:
            print(f"{Fore.LIGHTCYAN_EX}SSE tunnel local bind port: {sse_tunnel.local_bind_port}{Style.RESET_ALL}")
            print(f"{Fore.LIGHTCYAN_EX}Chat tunnel local bind port: {chat_tunnel.local_bind_port}{Style.RESET_ALL}")
            
            tunneled_url = f"http://127.0.0.1:{sse_tunnel.local_bind_port}{sse_endpoint}"
            print(f"{Fore.LIGHTCYAN_EX}Tunnels established. Connecting to SSE server at: {tunneled_url}{Style.RESET_ALL}")

            client = MCPClient(chat_tunnel)
            try:
                await client.connect_to_sse_server(server_url=tunneled_url)
                await client.chat_loop()
            finally:
                await client.cleanup()
    except Exception as e:
        print(f"{Fore.RED}Fatal error in main: {str(e)}{Style.RESET_ALL}")
        raise e

if __name__ == "__main__":
    asyncio.run(main())
