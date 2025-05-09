# This needs to be ran on ROSIE (MSOE's Supercomputer) and might be incorrect setup for a linux environment

# Setup

## Install UV

1. `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

## Create Virtual Environment

2. `uv venv`
3. `.venv\Scripts\activate`

## Install Dependencies

4. `uv install`

## Run Client

5. `python main.py`