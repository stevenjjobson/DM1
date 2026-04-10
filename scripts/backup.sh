#!/bin/bash
# DungeonMasterONE database backup script
# Run: /opt/dm1/scripts/backup.sh
# Cron: 0 3 * * * /opt/dm1/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="/opt/dm1/backups/$(date +%Y-%m-%d)"
COMPOSE_FILE="/opt/dm1/docker-compose.prod.yml"

mkdir -p "$BACKUP_DIR"

echo "=== DM1 Backup $(date) ==="

# MongoDB
echo "Backing up MongoDB..."
docker compose -f "$COMPOSE_FILE" exec -T mongodb mongodump --archive --gzip \
  > "$BACKUP_DIR/mongodb.archive.gz"

# Neo4j (dump via admin command)
echo "Backing up Neo4j..."
docker compose -f "$COMPOSE_FILE" exec -T neo4j neo4j-admin database dump neo4j \
  --to-stdout > "$BACKUP_DIR/neo4j.dump" 2>/dev/null || echo "Neo4j backup skipped (may need to stop DB)"

# Cleanup old backups (keep 7 days)
find /opt/dm1/backups -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

echo "Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
