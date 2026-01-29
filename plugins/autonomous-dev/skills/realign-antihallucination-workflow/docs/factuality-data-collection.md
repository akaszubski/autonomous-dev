# Stage 2: Factuality Data Collection

Collect factual data with proper citations and source attribution.

## Overview
Create dataset of factual claims with supporting sources.

## Data Sources
- Verified knowledge bases (Wikipedia, scientific papers)
- Fact-checking databases
- Curated factual datasets
- Expert-validated claims

## Process
1. Collect factual claims
2. Gather supporting sources
3. Create factual/unfactual pairs
4. Validate citation accuracy ≥85%

## Format
```jsonl
{"claim": "...", "source": "...", "factual": true, "citation": "..."}
```

## Quality Gate
- Citation accuracy ≥85%
- Diverse source types
- Clear attribution

**See**: `../templates.md` for data format examples.
