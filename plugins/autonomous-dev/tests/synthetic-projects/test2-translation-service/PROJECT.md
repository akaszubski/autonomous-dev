# Translation Service Project Documentation

**Last Updated**: 2024-09-01
**Version**: 1.5.0
**Status**: Development

## Project Vision

A simple proxy server for API format translation.

## Architecture Overview

Simple passthrough architecture with minimal processing.

### Known Issues

### 1. Stream Handling (CRITICAL ISSUE)

**Status**: CRITICAL ISSUE
**Discovered**: 2024-09-15

**Problem**:
Stream handling is broken. Data is buffered instead of streamed, causing memory issues with large payloads.

**Root Cause**:
Unknown. Still investigating the buffering behavior.

**Workaround**:
Limit payload size to 1MB for now.

### 2. Memory Leaks (WIP)

**Status**: WIP
**Discovered**: 2024-08-20

**Problem**:
Memory usage grows over time during long-running sessions.

**Root Cause**:
Event listeners not being cleaned up properly.

**Workaround**:
Restart service daily.

## Features

### Implemented
- ✅ Basic translation
- ✅ Error handling

### Coming Soon (Roadmap)
- 🔄 Advanced caching (planned for Q4 2024)
- 🔄 Multi-tenant support (planned for Q1 2025)

## Technology Stack

Compatible with v1.2.0 and above.

### Core Technologies
- Node.js 18.x
- Express 4.18
- TypeScript 5.2

## File Organization

Standard structure:
- src/ - Source code
- tests/ - Test files
- docs/ - Documentation
