#!/bin/bash

# ====================================
# PostgreSQL Docker 数据库备份脚本
# ====================================

# 配置参数
CONTAINER_NAME="windsurf-db-pro"          # Docker容器名称
BACKUP_DIR="/www/backup/postgresql"        # 备份存放目录
KEEP_DAYS=7                                # 保留最近N天的备份

# 从 .env 文件读取数据库信息（根据实际路径调整）
# 或者直接设置以下变量
POSTGRES_USER="${POSTGRES_USER:-user}"
POSTGRES_DB="${POSTGRES_DB:-windsurf_pool}"

# 生成备份文件名（包含日期时间）
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}_${DATE}.sql.gz"

# 创建备份目录（如果不存在）
mkdir -p ${BACKUP_DIR}

echo "=========================================="
echo "开始备份 PostgreSQL 数据库"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "容器: ${CONTAINER_NAME}"
echo "数据库: ${POSTGRES_DB}"
echo "=========================================="

# 执行备份命令
docker exec ${CONTAINER_NAME} pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} | gzip > ${BACKUP_FILE}

# 检查备份是否成功
if [ $? -eq 0 ] && [ -s ${BACKUP_FILE} ]; then
    FILESIZE=$(ls -lh ${BACKUP_FILE} | awk '{print $5}')
    echo "✅ 备份成功!"
    echo "文件: ${BACKUP_FILE}"
    echo "大小: ${FILESIZE}"
else
    echo "❌ 备份失败!"
    rm -f ${BACKUP_FILE}  # 删除空文件
    exit 1
fi

# 清理旧备份（保留最近N天）
echo ""
echo "清理 ${KEEP_DAYS} 天前的旧备份..."
find ${BACKUP_DIR} -name "*.sql.gz" -type f -mtime +${KEEP_DAYS} -delete

# 显示当前备份列表
echo ""
echo "当前备份文件:"
ls -lh ${BACKUP_DIR}/*.sql.gz 2>/dev/null || echo "暂无备份文件"

echo ""
echo "=========================================="
echo "备份任务完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
