# Project Rules

## Python Environment

- Use `D:\Anaconda3\envs\llm\python.exe` for all Python commands.
- Run tests with `D:\Anaconda3\envs\llm\python.exe -m pytest`.
- Install or inspect Python packages with `D:\Anaconda3\envs\llm\python.exe -m pip`.
- Do not use the system Python, another virtual environment, or an unqualified `python`/`pytest` command.

## Validation

- Run commands from the relevant project directory when package imports depend on the working directory.
- Prefer targeted tests first, then run the broader test suite when validating changes.
