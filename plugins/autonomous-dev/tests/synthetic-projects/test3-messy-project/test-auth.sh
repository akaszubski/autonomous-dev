#!/bin/bash
# Test authentication
# WRONG LOCATION: Should be in scripts/test/

echo "Testing authentication..."
curl http://localhost:3000/auth/login
