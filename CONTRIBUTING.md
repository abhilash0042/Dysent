# Contributing to DDoS Detection FL System

Thank you for considering contributing to our Privacy-Preserving Distributed DDoS Detection System!

## Getting Started

### Prerequisites

- Python 3.8+
- Git
- Virtual environment tool



### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/ddos-detection-fl.git
cd ddos-detection-fl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Code Style Guidelines

- Follow PEP 8 style guide
- Use type hints where applicable
- Write docstrings for all functions and classes
- Keep functions focused and under 50 lines when possible

## Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

## Commit Messages

Format: `[type]: Brief description`

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Testing
- `chore`: Build/CI changes

Example: `feat: Add SHAP feature selection method`

## Pull Request Process

1. Create a new branch from `main`
2. Make your changes
3. Write/update tests if applicable
4. Update documentation
5. Submit PR with clear description
6. Wait for code review

## Testing

```bash
# Run tests (when available)
pytest tests/

# Check code style
flake8 .
```

## Questions?

- Open an issue for questions
- Join our discussions for design decisions

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on collaboration
