#!/bin/bash

# Pre-commit Check Script
# Run this before committing to catch issues early

set -e

echo "🚀 ChatRaw Pre-Commit Checks"
echo "=============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
FAILED=0

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        FAILED=1
    fi
}

# 1. Check Python code style
echo "📝 Checking Python code style..."
if command -v black &> /dev/null; then
    cd backend
    black --check . || {
        echo -e "${YELLOW}⚠️  Python code needs formatting. Run: black backend/${NC}"
        FAILED=1
    }
    cd ..
    print_status 0 "Python formatting (Black)"
else
    echo -e "${YELLOW}⚠️  Black not installed. Install: pip install black${NC}"
fi

# 2. Check Python linting
echo ""
echo "🔍 Checking Python linting..."
if command -v flake8 &> /dev/null; then
    cd backend
    flake8 . && print_status 0 "Python linting (Flake8)" || print_status 1 "Python linting (Flake8)"
    cd ..
else
    echo -e "${YELLOW}⚠️  Flake8 not installed. Install: pip install flake8${NC}"
fi

# 3. Check JavaScript code style
echo ""
echo "🔍 Checking JavaScript code style..."
if [ -f "node_modules/.bin/eslint" ] || command -v eslint &> /dev/null; then
    npx eslint backend/static/**/*.js Plugins/**/*.js && \
        print_status 0 "JavaScript linting (ESLint)" || \
        print_status 1 "JavaScript linting (ESLint) - Run: npx eslint --fix"
else
    echo -e "${YELLOW}⚠️  ESLint not installed. Install: npm install --save-dev eslint${NC}"
fi

# 4. Check Markdown
echo ""
echo "📄 Checking Markdown files..."
if [ -f "node_modules/.bin/markdownlint" ] || command -v markdownlint &> /dev/null; then
    npx markdownlint '**/*.md' --ignore node_modules && \
        print_status 0 "Markdown linting" || \
        print_status 1 "Markdown linting"
else
    echo -e "${YELLOW}⚠️  Markdownlint not installed. Install: npm install --save-dev markdownlint-cli${NC}"
fi

# 5. Check for common security issues
echo ""
echo "🔒 Checking for common security issues..."

# Check for hardcoded secrets
echo "  - Checking for potential secrets..."
if grep -r -E "(api_key|password|secret|token|private_key)\s*=\s*['\"][^'\"]{8,}" \
    --include="*.py" --include="*.js" --exclude-dir=node_modules \
    --exclude-dir=.venv --exclude-dir=venv backend/ 2>/dev/null; then
    echo -e "${RED}❌ Potential hardcoded secrets found!${NC}"
    FAILED=1
else
    print_status 0 "No hardcoded secrets detected"
fi

# 6. Check Python dependencies for vulnerabilities
echo ""
echo "🛡️  Checking Python dependencies..."
if command -v safety &> /dev/null; then
    cd backend
    safety check --file requirements.txt --json > /dev/null 2>&1 && \
        print_status 0 "Python dependency security (Safety)" || \
        echo -e "${YELLOW}⚠️  Some dependency vulnerabilities found. Review with: safety check${NC}"
    cd ..
else
    echo -e "${YELLOW}⚠️  Safety not installed. Install: pip install safety${NC}"
fi

# 7. Check NPM dependencies
echo ""
echo "📦 Checking NPM dependencies..."
if [ -f "package.json" ]; then
    npm audit --production 2>&1 | grep -q "found 0 vulnerabilities" && \
        print_status 0 "NPM dependency security" || \
        echo -e "${YELLOW}⚠️  Some NPM vulnerabilities found. Review with: npm audit${NC}"
else
    echo "No package.json found, skipping..."
fi

# 8. Check Dockerfile
echo ""
echo "🐳 Checking Dockerfile..."
if command -v hadolint &> /dev/null; then
    hadolint Dockerfile && print_status 0 "Dockerfile linting (Hadolint)" || print_status 1 "Dockerfile linting"
else
    echo -e "${YELLOW}⚠️  Hadolint not installed. Install: brew install hadolint (macOS)${NC}"
fi

# Summary
echo ""
echo "=============================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo "You're ready to commit."
    exit 0
else
    echo -e "${RED}❌ Some checks failed!${NC}"
    echo "Please fix the issues above before committing."
    echo ""
    echo "Quick fix commands:"
    echo "  Python:     black backend/ && flake8 backend/"
    echo "  JavaScript: npx eslint --fix backend/static/**/*.js Plugins/**/*.js"
    echo "  Markdown:   npx markdownlint --fix '**/*.md' --ignore node_modules"
    exit 1
fi
