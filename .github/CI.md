# CI/CD Documentation

## Quick Start

```bash
# Local check
./scripts/pre-commit-check.sh

# Fix issues
black backend/
npx eslint --fix backend/static/**/*.js
```

## Workflows

| Workflow | Trigger | Checks |
|----------|---------|--------|
| code-quality.yml | PR | Python, JavaScript, Dockerfile, Markdown |
| codeql-analysis.yml | PR + Weekly | SQL injection, XSS, Path traversal |
| security-scan.yml | PR + Daily | CVE, Secrets, Misconfigurations |

**Trigger**: PR only, not on push (saves resources, quality ensured by branch protection)

## PR Comments

After creating a PR, you'll receive:
1. Initial status
2. Super Linter summary
3. ReviewDog inline comments
4. CodeQL security analysis
5. Trivy/Safety/NPM Audit
6. Final summary

## Configuration

- `.flake8` - Python
- `.eslintrc.json` - JavaScript
- `.markdownlint.json` - Markdown
- `.trivyignore` - Vulnerability whitelist

## Scheduled Scans

- CodeQL: Monday 02:00 UTC
- Trivy: Daily 03:00 UTC

Purpose: Discover newly disclosed CVEs

## Branch Protection

Settings → Branches → Add rule:
- Require pull request before merging
- Require status checks to pass

## Common Issues

**Code style errors**
```bash
black backend/
npx eslint --fix backend/static/**/*.js
```

**Dependency vulnerabilities**
```bash
pip install --upgrade <package>
npm audit fix
```

**Hardcoded secrets**
- Delete secrets
- Use environment variables
- Regenerate if leaked

**Why PR only?**
- PR comments only useful in PRs
- Saves resources
- Branch protection ensures quality
