#!/bin/bash

# Development Environment Setup Script
# Installs all necessary tools for local development

set -e

echo "🚀 ChatRaw Development Environment Setup"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"
echo ""

# 1. Check Python version
echo "1️⃣  Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✅ Python $PYTHON_VERSION installed${NC}"
else
    echo -e "${YELLOW}⚠️  Python 3 not found. Please install Python 3.12+${NC}"
    exit 1
fi

# 2. Check Node.js version
echo ""
echo "2️⃣  Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✅ Node.js $NODE_VERSION installed${NC}"
else
    echo -e "${YELLOW}⚠️  Node.js not found. Please install Node.js 20+${NC}"
    exit 1
fi

# 3. Install Python dependencies
echo ""
echo "3️⃣  Installing Python dependencies..."
cd backend
python3 -m pip install -r requirements.txt
echo -e "${GREEN}✅ Python dependencies installed${NC}"
cd ..

# 4. Install Python development tools
echo ""
echo "4️⃣  Installing Python development tools..."
python3 -m pip install black flake8 safety pylint
echo -e "${GREEN}✅ Python dev tools installed (black, flake8, safety, pylint)${NC}"

# 5. Install Node.js dependencies
echo ""
echo "5️⃣  Installing Node.js dependencies..."
npm install
echo -e "${GREEN}✅ Node.js dependencies installed${NC}"

# 6. Install Node.js development tools
echo ""
echo "6️⃣  Installing Node.js development tools..."
npm install --save-dev eslint markdownlint-cli
echo -e "${GREEN}✅ Node.js dev tools installed (eslint, markdownlint-cli)${NC}"

# 7. Install Hadolint (Dockerfile linter)
echo ""
echo "7️⃣  Installing Hadolint (Dockerfile linter)..."
if [ "$OS" = "Darwin" ]; then
    if command -v brew &> /dev/null; then
        brew install hadolint || echo -e "${YELLOW}⚠️  Hadolint installation skipped${NC}"
        echo -e "${GREEN}✅ Hadolint installed${NC}"
    else
        echo -e "${YELLOW}⚠️  Homebrew not found. Install from: https://brew.sh/${NC}"
        echo -e "${YELLOW}   Then run: brew install hadolint${NC}"
    fi
elif [ "$OS" = "Linux" ]; then
    echo "Downloading Hadolint binary..."
    wget -O /tmp/hadolint https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64
    chmod +x /tmp/hadolint
    sudo mv /tmp/hadolint /usr/local/bin/hadolint
    echo -e "${GREEN}✅ Hadolint installed${NC}"
else
    echo -e "${YELLOW}⚠️  Unsupported OS for automatic Hadolint installation${NC}"
    echo "   Download from: https://github.com/hadolint/hadolint/releases"
fi

# 8. Make scripts executable
echo ""
echo "8️⃣  Making scripts executable..."
chmod +x scripts/pre-commit-check.sh
chmod +x scripts/setup-dev.sh
echo -e "${GREEN}✅ Scripts are now executable${NC}"

# 9. Setup Git hooks (optional)
echo ""
echo "9️⃣  Setting up Git hooks..."
read -p "Would you like to setup a pre-commit hook? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p .git/hooks
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run pre-commit checks
./scripts/pre-commit-check.sh
EOF
    chmod +x .git/hooks/pre-commit
    echo -e "${GREEN}✅ Pre-commit hook installed${NC}"
    echo "   The pre-commit checks will run automatically before each commit"
else
    echo "Skipped pre-commit hook setup"
    echo "You can run checks manually with: ./scripts/pre-commit-check.sh"
fi

# Summary
echo ""
echo "========================================="
echo -e "${GREEN}✅ Development environment setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run the application:"
echo "     cd backend && python3 main.py"
echo ""
echo "  2. Before committing, run checks:"
echo "     ./scripts/pre-commit-check.sh"
echo ""
echo "  3. Check CI documentation:"
echo "     cat .github/CI.md"
echo ""
echo "Happy coding! 🎉"
