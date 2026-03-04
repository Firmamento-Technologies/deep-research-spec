#!/bin/bash
# =============================================================================
# DRS Database Seed Script
#
# Populates database with sample data for development/testing.
# =============================================================================

set -euo pipefail

echo "Seeding database with sample data..."

# Run Python seed script
docker-compose exec -T backend python -c "
import asyncio
from database.connection import get_db
from database.models import Run, Section
from datetime import datetime

async def seed():
    async for db in get_db():
        # Sample run
        run = Run(
            doc_id='sample-doc-1',
            topic='Machine Learning Fundamentals',
            status='complete',
            quality_preset='Balanced',
            target_words=3000,
            created_at=datetime.utcnow(),
        )
        db.add(run)
        
        # Sample sections
        section1 = Section(
            doc_id='sample-doc-1',
            section_idx=0,
            title='Introduction',
            content='Sample content...',
            status='complete',
        )
        db.add(section1)
        
        await db.commit()
        print('✓ Seed data inserted')
        break

asyncio.run(seed())
"

echo "Seed complete"
