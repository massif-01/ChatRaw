#!/bin/bash

# ChatRaw 插件系统快速测试脚本

echo "🧪 ChatRaw 插件系统测试脚本"
echo "================================"
echo ""

BASE_URL="${1:-http://localhost:51111}"
echo "测试目标: $BASE_URL"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
PASSED=0
FAILED=0

# 测试函数
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "测试: $name ... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    
    if [ "$response" == "$expected_status" ]; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败 (HTTP $response, 期望 $expected_status)${NC}"
        ((FAILED++))
        return 1
    fi
}

test_json() {
    local name=$1
    local url=$2
    local expected_key=$3
    
    echo -n "测试: $name ... "
    
    response=$(curl -s "$url" 2>/dev/null)
    
    if echo "$response" | grep -q "$expected_key"; then
        echo -e "${GREEN}✓ 通过${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        echo "  响应: $response"
        ((FAILED++))
        return 1
    fi
}

# 1. 基础健康检查
echo "📋 1. 基础健康检查"
echo "-------------------"
test_endpoint "健康检查" "$BASE_URL/health" 200
test_endpoint "就绪检查" "$BASE_URL/ready" 200
echo ""

# 2. 插件 API 测试
echo "📋 2. 插件 API 测试"
echo "-------------------"
test_endpoint "获取插件列表" "$BASE_URL/api/plugins" 200
test_json "插件列表格式" "$BASE_URL/api/plugins" "plugins\|\[\]"
echo ""

# 3. 插件市场测试
echo "📋 3. 插件市场测试"
echo "-------------------"
echo -n "测试: GitHub 插件市场索引 ... "
market_url="https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/index.json"
if curl -s --max-time 5 "$market_url" | grep -q "plugins"; then
    echo -e "${GREEN}✓ 通过${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ 警告 (网络可能无法访问 GitHub)${NC}"
    ((FAILED++))
fi
echo ""

# 4. 文件系统检查
echo "📋 4. 文件系统检查"
echo "-------------------"
if [ -d "Plugins/Plugin_market" ]; then
    echo -e "${GREEN}✓ 插件市场目录存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 插件市场目录不存在${NC}"
    ((FAILED++))
fi

if [ -f "Plugins/Plugin_market/index.json" ]; then
    echo -e "${GREEN}✓ 插件市场索引文件存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 插件市场索引文件不存在${NC}"
    ((FAILED++))
fi

if [ -d "Plugins/Plugin_market/excel-parser" ]; then
    echo -e "${GREEN}✓ Excel 解析器插件目录存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Excel 解析器插件目录不存在${NC}"
    ((FAILED++))
fi

if [ -f "Plugins/Plugin_market/excel-parser/manifest.json" ]; then
    echo -e "${GREEN}✓ Excel 解析器 manifest.json 存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Excel 解析器 manifest.json 不存在${NC}"
    ((FAILED++))
fi

if [ -f "Plugins/Plugin_market/excel-parser/main.js" ]; then
    echo -e "${GREEN}✓ Excel 解析器 main.js 存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Excel 解析器 main.js 不存在${NC}"
    ((FAILED++))
fi

if [ -f "Plugins/Plugin_market/excel-parser/icon.png" ]; then
    echo -e "${GREEN}✓ Excel 解析器图标存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Excel 解析器图标不存在${NC}"
    ((FAILED++))
fi
echo ""

# 5. 代码检查
echo "📋 5. 代码检查"
echo "-------------------"
if python3 -m py_compile backend/main.py 2>/dev/null; then
    echo -e "${GREEN}✓ Python 语法检查通过${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Python 语法错误${NC}"
    ((FAILED++))
fi

if [ -f "backend/static/app.js" ]; then
    echo -e "${GREEN}✓ app.js 存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ app.js 不存在${NC}"
    ((FAILED++))
fi

if [ -f "backend/static/index.html" ]; then
    echo -e "${GREEN}✓ index.html 存在${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ index.html 不存在${NC}"
    ((FAILED++))
fi
echo ""

# 总结
echo "================================"
echo "测试总结"
echo "================================"
echo -e "${GREEN}通过: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}失败: $FAILED${NC}"
else
    echo -e "${GREEN}失败: $FAILED${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    echo ""
    echo "下一步："
    echo "1. 启动服务器: cd backend && python main.py"
    echo "2. 访问 http://localhost:51111"
    echo "3. 打开浏览器开发者工具（F12）查看控制台"
    echo "4. 测试插件安装和 Excel 解析功能"
    exit 0
else
    echo -e "${YELLOW}⚠ 部分测试失败，请检查上述错误${NC}"
    exit 1
fi
