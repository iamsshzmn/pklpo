# 🧪 Testing Memory Optimization Features

This document explains how to test the memory optimization features we implemented.

## 📋 Test Files

### 1. **`quick_test.py`** - Quick Memory Test
- Tests memory usage comparison between streaming and non-streaming
- Tests performance metrics
- Tests parquet operations
- Tests configuration management
- **Run**: `python src/features/quick_test.py`

### 2. **`test_memory_optimization.py`** - Comprehensive Test Suite
- Tests all memory optimization components
- Tests streaming chunk processing
- Tests memory monitoring utilities
- Tests strategy lookback management
- Tests configuration management
- Tests parquet operations
- Tests database operations (mock)
- Tests performance metrics
- **Run**: `python src/features/test_memory_optimization.py`

### 3. **`test_cli.py`** - CLI Test Suite
- Tests all CLI commands
- Tests help commands
- Tests calculate command
- Tests validate command
- Tests test-parquet command
- Tests pipeline command
- **Run**: `python src/features/test_cli.py`

### 4. **`demo.py`** - Interactive Demo
- Demonstrates memory optimization in action
- Shows streaming vs non-streaming comparison
- Shows parquet operations
- Shows configuration and strategy lookbacks
- **Run**: `python src/features/demo.py`

### 5. **`run_tests.py`** - Test Runner
- Runs all tests with options
- Provides test summaries
- **Run**: `python src/features/run_tests.py [--quick|--cli|--all]`

## 🚀 Quick Start

### Run All Tests
```bash
# Run all tests
python src/features/run_tests.py

# Run only quick tests
python src/features/run_tests.py --quick

# Run only CLI tests
python src/features/run_tests.py --cli
```

### Run Individual Tests
```bash
# Quick memory test
python src/features/quick_test.py

# Full test suite
python src/features/test_memory_optimization.py

# CLI tests
python src/features/test_cli.py

# Interactive demo
python src/features/demo.py
```

## 🔧 Test Configuration

### Environment Variables
```bash
# Set test parameters
export FEATURES_CHUNKSIZE=1000
export FEATURES_MAX_LOOKBACK=50
export FEATURES_OVERLAP_SIZE=50
export FEATURES_INSERT_CHUNKSIZE=500
export FEATURES_FORCE_GC_AFTER_CHUNK=true
export FEATURES_CLEAR_INTERMEDIATE_OBJECTS=true
export FEATURES_LOG_MEMORY_USAGE=true
export FEATURES_VERBOSE_LOGGING=true
```

### Test Data
- **Default size**: 10,000 rows
- **Chunk size**: 2,000 rows
- **Indicators**: hlc3, ema_8, sma_20, rsi_14, atr_14
- **Timeframe**: 1H
- **Symbol**: TEST

## 📊 Expected Results

### Memory Usage
- **Streaming should use less memory** than non-streaming
- **Peak memory should be lower** with streaming
- **Memory should not grow linearly** with input size

### Performance
- **Streaming may be slightly slower** due to overhead
- **Performance should be acceptable** (>80% of non-streaming)
- **Throughput should be stable** across chunks

### Data Quality
- **Results should be equivalent** (within tolerance)
- **First MAX_LOOKBACK-1 rows may differ** (expected)
- **All indicators should be calculated correctly**

## 🐛 Troubleshooting

### Common Issues

#### 1. **Import Errors**
```bash
# Add parent directory to path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

#### 2. **Memory Issues**
```bash
# Increase memory limit
export FEATURES_CHUNKSIZE=500
export FEATURES_MAX_LOOKBACK=25
```

#### 3. **Timeout Issues**
```bash
# Increase timeout
export FEATURES_BATCH_TIMEOUT_SECONDS=600
```

#### 4. **Database Connection Issues**
```bash
# Use mock database
export FEATURES_USE_MOCK_DATABASE=true
```

### Debug Mode
```bash
# Enable debug logging
export FEATURES_VERBOSE_LOGGING=true
export FEATURES_LOG_MEMORY_USAGE=true
export FEATURES_LOG_DF_SHAPES=true
```

## 📈 Performance Benchmarks

### Expected Performance
- **Memory improvement**: 30-50% reduction
- **Peak memory improvement**: 40-60% reduction
- **Performance**: 80-120% of non-streaming
- **Throughput**: 1000-5000 rows/second

### Test Scenarios
1. **Small dataset** (1,000 rows): Quick validation
2. **Medium dataset** (10,000 rows): Standard testing
3. **Large dataset** (100,000 rows): Stress testing
4. **Very large dataset** (1,000,000 rows): Memory limit testing

## 🔍 Test Validation

### Memory Validation
- ✅ Peak memory does not grow linearly
- ✅ Streaming uses less memory than non-streaming
- ✅ Memory is freed after each chunk
- ✅ Garbage collection is working

### Data Validation
- ✅ Results are equivalent (within tolerance)
- ✅ All indicators are calculated correctly
- ✅ Chunk overlap is handled properly
- ✅ No data loss between chunks

### Performance Validation
- ✅ Performance is acceptable (>80% of non-streaming)
- ✅ Throughput is stable across chunks
- ✅ No memory leaks or accumulation
- ✅ Configuration parameters work correctly

## 📝 Test Reports

### Memory Optimization Report
- **Location**: `src/features/MEMORY_OPTIMIZATION_REPORT.md`
- **Content**: Memory anti-patterns, solutions, performance improvements
- **Status**: ✅ Complete

### Pull Request
- **Location**: `src/features/PULL_REQUEST.md`
- **Content**: All changes, problems, solutions, testing
- **Status**: ✅ Complete

### Test Results
- **Location**: Console output
- **Content**: Real-time test results and metrics
- **Status**: ✅ Available

## 🎯 Success Criteria

### Memory Optimization
- ✅ Peak memory does not grow linearly with input size
- ✅ Streaming version produces same values as "whole" (except first MAX_LOOKBACK-1 rows)
- ✅ Stable average TPS for insertion
- ✅ Batch transactions commit without rollback

### Performance
- ✅ Memory usage is optimized
- ✅ Streaming processing works correctly
- ✅ Configuration management works
- ✅ Strategy lookbacks are correct
- ✅ Parquet operations work
- ✅ Database operations are optimized
- ✅ Performance metrics are good

## 🚀 Next Steps

1. **Run tests** to validate implementation
2. **Review results** and fix any issues
3. **Deploy to production** with monitoring
4. **Monitor performance** in production
5. **Optimize further** based on real-world usage

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the test output for specific errors
3. Check the configuration parameters
4. Verify all dependencies are installed
5. Contact the development team for assistance

---

**Happy Testing! 🧪✨**
