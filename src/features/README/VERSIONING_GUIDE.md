# Versioning Guide - ML Reproducibility (FEAT-001)

**Feature:** ML Model Reproducibility through Calculation Versioning  
**Version:** 1.0  
**Status:** ✅ Implemented  

---

## 📋 Overview

The versioning system enables ML engineers to track, reproduce, and audit feature calculations, ensuring that machine learning models can reliably reproduce their training data.

### Key Benefits

- **🔄 Reproducibility**: Exact recreation of feature calculations
- **📊 Auditability**: Complete history of all calculations
- **🎯 Traceability**: Link models to specific data versions
- **🔍 Debugging**: Identify when algorithms changed
- **📈 Evolution Tracking**: Monitor algorithm improvements over time

---

## 🎯 Core Concepts

### 1. Snapshot

A **snapshot** is a complete record of a feature calculation run, including:
- Configuration used
- Algorithm version
- Symbols and timeframes processed
- Execution statistics
- Status tracking

### 2. Algorithm Version

Each calculation is tagged with an **algorithm version** hash that uniquely identifies:
- Core calculation logic
- Normalization methods
- Feature specifications

### 3. Calculation Metadata

Metadata stored for each snapshot includes:
- When it was created/completed
- How many rows were calculated
- What configuration was used
- Any errors that occurred

---

## 🚀 Quick Start

### Creating a Snapshot

```python
from src.features.versioning import create_calculation_snapshot, snapshot_manager
from src.database import get_async_session

async def calculate_with_tracking():
    async with get_async_session() as session:
        # Create snapshot before calculation
        snapshot_id = await create_calculation_snapshot(
            session,
            symbols=['BTC-USDT-SWAP', 'ETH-USDT-SWAP'],
            timeframes=['1H', '4H'],
            features=None,  # All features
            volatility_normalize=True,
            normalize_window=20
        )

        print(f"Created snapshot: {snapshot_id}")

        try:
            # Perform your calculations
            # ... your calculation code ...

            rows_calculated = 10000
            duration_seconds = 45.2

            # Mark snapshot as completed
            await snapshot_manager.complete_snapshot(
                session,
                snapshot_id,
                rows_calculated=rows_calculated,
                duration_seconds=duration_seconds
            )

            print(f"✅ Snapshot completed: {rows_calculated} rows in {duration_seconds}s")

        except Exception as e:
            # Mark snapshot as failed
            await snapshot_manager.fail_snapshot(
                session,
                snapshot_id,
                error_message=str(e)
            )
            raise
```

### Saving Data with Versioning

```python
from src.features.save import save_batch
from src.database import get_async_session

async def save_with_version():
    async with get_async_session() as session:
        await save_batch(
            session,
            df=features_df,
            symbol='BTC-USDT-SWAP',
            timeframe='1H',
            snapshot_id='snap_20251027_123456_abc12345',  # Link to snapshot
            algorithm_version='1.0.0'  # Or auto-detected
        )
```

---

## 🔧 CLI Commands

### List Snapshots

```bash
# List all snapshots
python -m src.features.cli snapshots-list

# List only completed snapshots
python -m src.features.cli snapshots-list --status completed

# Limit results
python -m src.features.cli snapshots-list --limit 10

# Filter by algorithm version
python -m src.features.cli snapshots-list --version algo_v12345678
```

**Output Example:**
```
📸 Found 5 snapshot(s):

ID                        Created              Status       Version      Rows  
=====================================================================================
snap_20251027_143052_a1b2 2025-10-27 14:30:52 completed    algo_v1234   10000  
snap_20251027_120015_c3d4 2025-10-27 12:00:15 completed    algo_v1234   8500  
snap_20251026_180945_e5f6 2025-10-26 18:09:45 failed       algo_v1234   0  
snap_20251026_150230_g7h8 2025-10-26 15:02:30 completed    algo_v1234   12000  
snap_20251026_091145_i9j0 2025-10-26 09:11:45 in_progress  algo_v1234   5000
```

### Show Snapshot Details

```bash
# Show snapshot information
python -m src.features.cli snapshots-show snap_20251027_143052_a1b2

# Show with configuration details
python -m src.features.cli snapshots-show snap_20251027_143052_a1b2 --show-config
```

**Output Example:**
```
📸 Snapshot: snap_20251027_143052_a1b2

Status: completed
Created: 2025-10-27T14:30:52.123456+00:00
Completed: 2025-10-27T14:31:37.654321+00:00
Algorithm Version: algo_v12345678
Module Version: 1.0.0
Rows Calculated: 10,000
Duration: 45.53s

Symbols (2): BTC-USDT-SWAP, ETH-USDT-SWAP

Timeframes (2): 1H, 4H

📝 Configuration:
{
  "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
  "timeframes": ["1H", "4H"],
  "features": [],
  "volatility_normalize": true,
  "normalize_window": 20,
  "normalize_method": "rolling_std"
}
```

---

## 📊 Database Schema

### indicators Table

New columns added:

```sql
ALTER TABLE indicators
  ADD COLUMN algorithm_version VARCHAR(20) DEFAULT '1.0.0',
  ADD COLUMN snapshot_id VARCHAR(50),
  ADD COLUMN calculation_config JSONB,
  ADD COLUMN calculated_at TIMESTAMP WITH TIME ZONE;
```

### calculation_metadata Table

```sql
CREATE TABLE calculation_metadata (
  snapshot_id VARCHAR(50) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  algorithm_version VARCHAR(20) NOT NULL,
  module_version VARCHAR(20) NOT NULL,
  config JSONB NOT NULL,
  symbols TEXT[],
  timeframes TEXT[],
  status VARCHAR(20) DEFAULT 'in_progress',
  rows_calculated INTEGER DEFAULT 0,
  execution_duration_seconds NUMERIC(10, 2),
  error_message TEXT
);
```

### v_calculation_summary View

Convenient view for querying snapshots:

```sql
SELECT * FROM v_calculation_summary
WHERE status = 'completed'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🔍 Query Examples

### Find Calculations by Algorithm Version

```python
async def find_by_version(session, version: str):
    from src.features.versioning import snapshot_manager

    snapshots = await snapshot_manager.list_snapshots(
        session,
        algorithm_version=version,
        limit=100
    )

    return snapshots
```

### Reproduce a Calculation

```python
async def reproduce_calculation(session, snapshot_id: str):
    """Reproduce a calculation from its snapshot."""
    from src.features.versioning import snapshot_manager
    from src.features.core import compute_features
    import json

    # Get snapshot details
    snapshot = await snapshot_manager.get_snapshot(session, snapshot_id)

    if not snapshot:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    # Extract configuration
    config = snapshot['config']
    symbols = snapshot['symbols']
    timeframes = snapshot['timeframes']

    print(f"Reproducing calculation from {snapshot['created_at']}")
    print(f"Algorithm version: {snapshot['algorithm_version']}")
    print(f"Configuration: {json.dumps(config, indent=2)}")

    # Reproduce calculation with exact same parameters
    # ... fetch OHLCV data ...
    # ... compute features with config ...
    # ... compare results ...
```

### Find Calculations for a Model Training

```python
async def get_training_snapshots(
    session,
    start_date: datetime,
    end_date: datetime
):
    """Get all successful calculations in a date range."""
    from sqlalchemy import select, and_
    from src.models import CalculationMetadata

    stmt = select(CalculationMetadata).where(
        and_(
            CalculationMetadata.status == 'completed',
            CalculationMetadata.created_at >= start_date,
            CalculationMetadata.created_at <= end_date
        )
    ).order_by(CalculationMetadata.created_at)

    result = await session.execute(stmt)
    snapshots = result.scalars().all()

    return snapshots
```

---

## 🎓 Best Practices

### 1. Always Create Snapshots for Production Calculations

```python
# ✅ GOOD
snapshot_id = await create_calculation_snapshot(...)
# ... calculate ...
await snapshot_manager.complete_snapshot(...)

# ❌ BAD
# ... calculate without snapshot ...
```

### 2. Include Meaningful Configuration

```python
# ✅ GOOD
snapshot_id = await create_calculation_snapshot(
    session,
    symbols=['BTC-USDT-SWAP'],
    timeframes=['1H'],
    features=['rsi_14', 'sma_50'],  # Specific features
    volatility_normalize=True,
    normalize_window=20
)

# ❌ BAD
snapshot_id = await create_calculation_snapshot(
    session,
    symbols=[],  # Empty!
    timeframes=[],  # Empty!
)
```

### 3. Handle Failures Gracefully

```python
try:
    # Calculation logic
    pass
except Exception as e:
    # Always mark snapshot as failed
    await snapshot_manager.fail_snapshot(
        session,
        snapshot_id,
        error_message=str(e)
    )
    raise
```

### 4. Query by Completion Status

```python
# Get only successful calculations
successful_snapshots = await snapshot_manager.list_snapshots(
    session,
    status='completed',
    limit=100
)

# Get failed calculations for debugging
failed_snapshots = await snapshot_manager.list_snapshots(
    session,
    status='failed',
    limit=10
)
```

---

## 🔧 Administration

### Apply Migration

```bash
# Check current status
python src/database/migrations/apply_versioning_migration.py --status

# Dry run (see what would be executed)
python src/database/migrations/apply_versioning_migration.py --dry-run

# Apply migration
python src/database/migrations/apply_versioning_migration.py
```

### Rollback Migration (if needed)

```bash
# Rollback (removes all versioning)
python src/database/migrations/apply_versioning_migration.py --rollback --dry-run
python src/database/migrations/apply_versioning_migration.py --rollback
```

### Clean Up Old Snapshots

```sql
-- Delete snapshots older than 90 days
DELETE FROM calculation_metadata
WHERE created_at < NOW() - INTERVAL '90 days'
AND status IN ('completed', 'failed');

-- Or keep only last N snapshots per symbol
-- (Custom SQL based on your retention policy)
```

---

## 🐛 Troubleshooting

### Problem: Migration fails with "column already exists"

**Solution:** The migration has been partially applied. Check status:

```bash
python src/database/migrations/apply_versioning_migration.py --status
```

If partially applied, manually complete or rollback and reapply.

### Problem: Snapshot ID not being saved

**Check:**
1. Is `snapshot_id` parameter passed to `save_batch()`?
2. Is the migration applied?
3. Check database logs for constraint errors

### Problem: Can't find snapshot

**Check:**
1. Correct snapshot_id format (snap_YYYYMMDD_HHMMSS_HASH)
2. Snapshot was committed to database
3. Database connection is correct

---

## 📚 API Reference

### SnapshotManager

```python
class SnapshotManager:
    async def create_snapshot(
        session,
        config: SnapshotConfig,
        snapshot_id: Optional[str] = None
    ) -> str

    async def update_snapshot_progress(
        session,
        snapshot_id: str,
        rows_calculated: int
    )

    async def complete_snapshot(
        session,
        snapshot_id: str,
        rows_calculated: int,
        duration_seconds: float
    )

    async def fail_snapshot(
        session,
        snapshot_id: str,
        error_message: str
    )

    async def get_snapshot(
        session,
        snapshot_id: str
    ) -> Optional[Dict[str, Any]]

    async def list_snapshots(
        session,
        limit: int = 50,
        status: Optional[str] = None,
        algorithm_version: Optional[str] = None
    ) -> List[Dict[str, Any]]
```

### SnapshotConfig

```python
@dataclass
class SnapshotConfig:
    symbols: List[str]
    timeframes: List[str]
    features: List[str]
    volatility_normalize: bool = True
    normalize_window: int = 20
    normalize_method: str = "rolling_std"
```

---

## 🎯 Use Cases

### Use Case 1: ML Model Training

```python
# Record which data was used for training
snapshot_id = await create_calculation_snapshot(...)
# ... train model ...
model_metadata = {
    'model_id': 'model_v1',
    'training_snapshot': snapshot_id,
    'trained_at': datetime.now()
}
# Save model_metadata for reproducibility
```

### Use Case 2: A/B Testing Algorithm Changes

```python
# Before algorithm change
old_version_snapshots = await snapshot_manager.list_snapshots(
    session,
    algorithm_version='algo_v1'
)

# After algorithm change
new_version_snapshots = await snapshot_manager.list_snapshots(
    session,
    algorithm_version='algo_v2'
)

# Compare results
```

### Use Case 3: Debugging Production Issues

```python
# Find calculation that caused issue
snapshot = await snapshot_manager.get_snapshot(
    session,
    'snap_20251027_143052_a1b2'
)

# Check configuration, status, error_message
# Reproduce locally with exact same config
```

---

## 📖 Related Documentation

- [RECOMMENDATIONS_AUDIT.md](./RECOMMENDATIONS_AUDIT.md) - Architecture audit
- [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) - Implementation plan
- [FEAT-001_PROGRESS.md](./FEAT-001_PROGRESS.md) - Development progress
- [COMPREHENSIVE_DOCUMENTATION.md](./COMPREHENSIVE_DOCUMENTATION.md) - Full module docs

---

**Version:** 1.0  
**Last Updated:** 2025-10-27  
**Status:** ✅ Production Ready
