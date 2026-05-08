#!/bin/bash
# ==================================================
# 生产环境配置验证脚本
# ==================================================

echo "🔍 生产环境配置验证"
echo "===================="
echo ""

# 检查文件是否存在
if [ ! -f ".env.prod" ]; then
    echo "❌ 错误：.env.prod 文件不存在"
    echo "   请先创建：cp .env.prod.example .env.prod"
    exit 1
fi

echo "✅ .env.prod 文件已存在"
echo ""

# 检查关键配置
echo "📋 关键配置检查："
echo ""

# 1. 检查SECRET_KEY强度
SECRET_KEY=$(grep "^SECRET_KEY=" .env.prod | cut -d'=' -f2)
if [ ${#SECRET_KEY} -ge 32 ]; then
    echo "✅ SECRET_KEY: 强度合格 (${#SECRET_KEY}字节)"
else
    echo "❌ SECRET_KEY: 强度不足 (${#SECRET_KEY}字节，需>=32)"
    echo "   生成新密钥：python -c \"import secrets; print(secrets.token_urlsafe(32))\""
fi

# 2. 检查POSTGRES_PASSWORD强度
POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" .env.prod | cut -d'=' -f2)
if [ ${#POSTGRES_PASSWORD} -ge 16 ]; then
    echo "✅ POSTGRES_PASSWORD: 强度合格 (${#POSTGRES_PASSWORD}字节)"
else
    echo "❌ POSTGRES_PASSWORD: 强度不足 (${#POSTGRES_PASSWORD}字节，需>=16)"
fi

# 3. 检查DEBUG设置
DEBUG=$(grep "^DEBUG=" .env.prod | cut -d'=' -f2)
if [ "$DEBUG" = "false" ]; then
    echo "✅ DEBUG: 已正确设置为 false"
else
    echo "❌ DEBUG: 应设置为 false（生产环境不应开启调试）"
fi

# 4. 检查ENVIRONMENT设置
ENVIRONMENT=$(grep "^ENVIRONMENT=" .env.prod | cut -d'=' -f2)
if [ "$ENVIRONMENT" = "production" ]; then
    echo "✅ ENVIRONMENT: 已正确设置为 production"
else
    echo "❌ ENVIRONMENT: 应设置为 production"
fi

echo ""
echo "⚠️ 需要手动修改的配置："
echo ""

# 5. 检查CORS_ORIGINS
CORS_ORIGINS=$(grep "^CORS_ORIGINS=" .env.prod | cut -d'=' -f2)
if [[ "$CORS_ORIGINS" == *"your-domain.com"* ]]; then
    echo "❌ CORS_ORIGINS: 包含示例域名，必须修改为真实生产域名"
    echo "   当前值：$CORS_ORIGINS"
else
    echo "✅ CORS_ORIGINS: 已配置为 $CORS_ORIGINS"
fi

# 6. 检查OKX API密钥
OKX_API_KEY=$(grep "^OKX_API_KEY=" .env.prod | cut -d'=' -f2)
if [[ "$OKX_API_KEY" == *"your-"* ]]; then
    echo "❌ OKX_API_KEY: 包含示例值，必须填入真实密钥"
else
    echo "✅ OKX_API_KEY: 已配置（值已隐藏）"
fi

# 7. 检查LLM API密钥
LLM_API_KEY=$(grep "^LLM_API_KEY=" .env.prod | cut -d'=' -f2)
if [[ "$LLM_API_KEY" == *"your-"* ]]; then
    echo "❌ LLM_API_KEY: 包含示例值，必须填入真实密钥"
else
    echo "✅ LLM_API_KEY: 已配置（值已隐藏）"
fi

echo ""
echo "===================="

# 总结
ERRORS=0
if [ ${#SECRET_KEY} -lt 32 ]; then ERRORS=$((ERRORS+1)); fi
if [ ${#POSTGRES_PASSWORD} -lt 16 ]; then ERRORS=$((ERRORS+1)); fi
if [ "$DEBUG" != "false" ]; then ERRORS=$((ERRORS+1)); fi
if [ "$ENVIRONMENT" != "production" ]; then ERRORS=$((ERRORS+1)); fi
if [[ "$CORS_ORIGINS" == *"your-domain.com"* ]]; then ERRORS=$((ERRORS+1)); fi
if [[ "$OKX_API_KEY" == *"your-"* ]]; then ERRORS=$((ERRORS+1)); fi
if [[ "$LLM_API_KEY" == *"your-"* ]]; then ERRORS=$((ERRORS+1)); fi

if [ $ERRORS -eq 0 ]; then
    echo "✅ 所有配置验证通过！"
    echo "   可以开始部署："
    echo "   docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d"
else
    echo "❌ 发现 $ERRORS 个配置问题"
    echo "   请修改 .env.prod 文件后再部署"
fi

echo ""
echo "💡 快速密钥生成命令："
echo "   SECRET_KEY:        python -c \"import secrets; print(secrets.token_urlsafe(32))\""
echo "   POSTGRES_PASSWORD: python -c \"import secrets; print(secrets.token_urlsafe(16))\""