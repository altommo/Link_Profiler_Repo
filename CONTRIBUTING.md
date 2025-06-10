# 🤝 Contributing to Link Profiler

We welcome contributions from the community! Whether it's a bug report, a new feature, or an improvement to existing code, your input is highly valued. Please take a moment to review this document to make the contribution process as smooth as possible.

## Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project, you agree to abide by its terms.

## How Can I Contribute?

### Reporting Bugs

*   **Check existing issues**: Before submitting a new bug report, please check the [issue tracker](https://github.com/your-org/link-profiler/issues) to see if the bug has already been reported.
*   **Provide detailed information**: When reporting a bug, please include:
    *   A clear and concise description of the bug.
    *   Steps to reproduce the behaviour.
    *   Expected behaviour.
    *   Actual behaviour.
    *   Screenshots or error messages (if applicable).
    *   Your operating system, Python version, and any relevant dependencies.

### Suggesting Enhancements

*   **Check existing issues**: Before suggesting an enhancement, please check the [issue tracker](https://github.com/your-org/link-profiler/issues) to see if it has already been proposed.
*   **Describe your idea**: Clearly explain the enhancement, its benefits, and how it would fit into the existing system. Provide use cases if possible.

### Contributing Code

We follow a standard GitHub pull request workflow.

1.  **Fork the repository**: Start by forking the `link-profiler` repository to your GitHub account.
2.  **Clone your fork**:
    ```bash
    git clone https://github.com/your-username/link-profiler.git
    cd link-profiler
    ```
3.  **Create a new branch**: Create a new branch for your feature or bug fix. Use a descriptive name (e.g., `feature/add-ai-summary` or `fix/broken-link-detection`).
    ```bash
    git checkout -b feature/your-feature-name
    ```
4.  **Set up your development environment**:
    *   Ensure you have Python 3.8+ installed.
    *   Create and activate a virtual environment:
        ```bash
        python -m venv venv
        source venv/bin/activate # On Windows: venv\Scripts\activate
        ```
    *   Install dependencies:
        ```bash
        pip install -r requirements.txt
        pip install -r requirements-dev.txt # For development tools like pytest, black, flake8
        ```
    *   Install pre-commit hooks:
        ```bash
        pre-commit install
        ```
5.  **Make your changes**: Implement your feature or fix.
    *   **Code Style**: Adhere to [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code. We use `black` for formatting and `flake8` for linting (enforced by pre-commit hooks).
    *   **Type Hinting**: Use type hints for all functions and variables.
    *   **Docstrings**: Write clear and concise docstrings for all new functions, classes, and modules.
    *   **Tests**: Write unit and integration tests for your changes. Ensure existing tests pass.
        ```bash
        pytest tests/
        ```
    *   **Logging**: Use the `logging` module for informative messages.
    *   **Configuration**: If new configuration options are needed, add them to the relevant `Link_Profiler/config/*.yaml` file and update `ConfigLoader`.
    *   **Multi-tenancy**: If your changes involve data storage or retrieval, ensure `user_id` and `organization_id` are correctly handled for multi-tenancy.
6.  **Commit your changes**: Write clear, concise commit messages. Follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification (e.g., `feat: Add new feature`, `fix: Resolve bug`).
    ```bash
    git add .
    git commit -m "feat: Add a brief description of your changes"
    ```
7.  **Push to your fork**:
    ```bash
    git push origin feature/your-feature-name
    ```
8.  **Open a Pull Request (PR)**:
    *   Go to the original `link-profiler` repository on GitHub.
    *   You should see a prompt to create a new pull request from your recently pushed branch.
    *   Provide a clear title and detailed description of your changes. Reference any related issues.
    *   Ensure all checks (CI/CD, linting, tests) pass.

## Development Guidelines

*   **Asynchronous Programming**: All network I/O and long-running tasks should be asynchronous using `asyncio` and `await`.
*   **Dependency Injection**: Services and clients should generally receive their dependencies (like `SessionManager`, `RedisClient`, `Database`) via their constructors, rather than importing global singletons directly within their class bodies. This improves testability and modularity.
*   **Error Handling**: Implement robust error handling, logging, and appropriate exceptions.
*   **Prometheus Metrics**: If adding new functionality that involves measurable operations (API calls, database writes, job processing), consider adding relevant Prometheus metrics in `Link_Profiler/monitoring/prometheus_metrics.py`.

Thank you for contributing to Link Profiler!
