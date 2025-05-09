# NLP Final Project - AI Coding Assistant

This project implements an AI coding assistant that can help with various programming tasks. It consists of a client-server architecture where the server runs on ROSIE (MSOE's Supercomputer) and the client can connect to it remotely.

## Features

- Clone GitHub repositories
- Search for code in repositories
- Add files to context
- Get file structure
- View READMEs from GitHub repositories
- AI-powered code assistance

## Project Structure

- `client/` - Client-side code for connecting to the server
- `server/` - Server-side code running on ROSIE

## Setup Instructions

### Server Setup (on ROSIE)

See [server/README.md](server/README.md) for detailed instructions on setting up the server on ROSIE.

### Client Setup

See [client/README.md](client/README.md) for detailed instructions on setting up the client on your local machine.

## Usage

1. Start the server on ROSIE
2. Connect to the server using the client
3. Use the available commands to interact with the AI assistant:
   - `/lr` - List available repositories
   - `/fs <path>` - Gets file repository's structure
   - `/ac <path>` - Adds one file to context
   - `/search <query>` - Search GitHub repositories
   - `/readme <owner/repo>` - Get README for a GitHub repository
   - `/clone <repo_url>` - Clone a GitHub repository

## Technologies Used

- Python
- OpenAI API
- SSH Tunneling
- MCP (Model Communication Protocol)
- Git
