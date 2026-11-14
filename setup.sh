#!/bin/bash
# 即梦平台插件快速安装脚本

set -e

echo "=================================================="
echo "即梦平台插件安装脚本"
echo "=================================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="/Users/admin/Desktop/myapps/any-auto-register"

cd "$PROJECT_DIR"

echo ""
echo "1. 检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 || echo "Python 3 not found")
echo "   当前版本：$PYTHON_VERSION"

if [[ "$PYTHON_VERSION" == *"3.8"* ]]; then
    echo -e "${YELLOW}⚠️  检测到 Python 3.8，需要 Python 3.11+${NC}"
    echo ""
    echo "请选择安装方式："
    echo "1) 使用 Homebrew 安装 Python 3.11"
    echo "2) 使用 pyenv 安装 Python 3.11"
    echo "3) 使用 Docker（推荐，最简单）"
    echo "4) 跳过，手动安装"
    echo ""
    read -p "请选择 [1-4]: " choice

    case $choice in
        1)
            echo ""
            echo "2. 使用 Homebrew 安装 Python 3.11..."
            if ! command -v brew &> /dev/null; then
                echo -e "${RED}❌ Homebrew 未安装${NC}"
                echo "请先安装 Homebrew:"
                echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
                exit 1
            fi

            echo "   安装 Python 3.11..."
            brew install python@3.11

            echo "   验证安装..."
            python3.11 --version || {
                echo -e "${RED}❌ Python 3.11 安装失败${NC}"
                exit 1
            }

            PYTHON_CMD="python3.11"
            ;;
        2)
            echo ""
            echo "2. 使用 pyenv 安装 Python 3.11..."
            if ! command -v pyenv &> /dev/null; then
                echo "   安装 pyenv..."
                brew install pyenv
            fi

            echo "   安装 Python 3.11.7..."
            pyenv install 3.11.7
            pyenv local 3.11.7

            PYTHON_CMD="python"
            ;;
        3)
            echo ""
            echo "2. 使用 Docker 安装..."
            if ! command -v docker &> /dev/null; then
                echo -e "${RED}❌ Docker 未安装${NC}"
                echo "请先安装 Docker Desktop"
                exit 1
            fi

            echo "   构建 Docker 镜像..."
            docker build -t any-auto-register .

            echo ""
            echo -e "${GREEN}✅ Docker 镜像构建完成${NC}"
            echo ""
            echo "运行容器："
            echo "  docker run -d \\"
            echo "    --name any-auto-register \\"
            echo "    -p 8000:8000 \\"
            echo "    -p 6080:6080 \\"
            echo "    -p 8889:8889 \\"
            echo "    -v \$(pwd)/data:/app/data \\"
            echo "    any-auto-register"
            echo ""
            echo "访问："
            echo "  Web UI: http://localhost:8000"
            echo "  noVNC: http://localhost:6080/vnc.html"
            exit 0
            ;;
        4)
            echo ""
            echo "   跳过自动安装，请手动安装 Python 3.11+"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 无效选择${NC}"
            exit 1
            ;;
    esac
else
    PYTHON_CMD="python3"
fi

echo ""
echo "3. 创建虚拟环境..."
$PYTHON_CMD -m venv .venv || {
    echo -e "${RED}❌ 虚拟环境创建失败${NC}"
    exit 1
}

echo "   激活虚拟环境..."
source .venv/bin/activate

echo ""
echo "4. 升级 pip..."
pip install --upgrade pip

echo ""
echo "5. 安装依赖..."
pip install -r requirements.txt || {
    echo -e "${RED}❌ 依赖安装失败${NC}"
    echo "   请检查 requirements.txt 或网络连接"
    exit 1
}

echo ""
echo "6. 安装 Playwright 浏览器..."
python -m playwright install chromium || {
    echo -e "${YELLOW}⚠️  Playwright 安装失败，可以稍后手动安装${NC}"
    echo "   命令：python -m playwright install chromium"
}

echo ""
echo "7. 运行结构验证测试..."
python test_plugin_structure.py

echo ""
echo "=================================================="
echo -e "${GREEN}✅ 安装完成！${NC}"
echo "=================================================="
echo ""
echo "下一步："
echo "1. 启动服务："
echo "   python -m uvicorn main:app --port 8000"
echo ""
echo "2. 访问 Web UI："
echo "   http://localhost:8000"
echo ""
echo "3. 查看文档："
echo "   platforms/jimeng/README.md"
echo "   INSTALL_GUIDE.md"
echo ""
echo "4. 同步账号池："
echo "   python tools/jimeng_pool_sync.py"
echo ""
echo "=================================================="
