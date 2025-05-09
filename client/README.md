# Setup

## Install UV

1. `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

## Copy over Envirnoment Variables

2. Rename `.env.example` to `.env`
3. Put your ROSIE login and password
    - `HPC_USERNAME` = Your ROSIE login
    - `HPC_PASSWORD` = Your ROSIE password
    - Is this safe? Yes unless you share your `.env` file

## Create Virtual Environment

4. `uv venv`
5. `.venv\Scripts\activate`

## Install Dependencies

6. `uv install`

## Run Client

7. `python main.py`