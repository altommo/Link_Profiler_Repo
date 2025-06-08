#!/bin/bash
# Export environment variables for Link Profiler

export LP_DATABASE_URL="postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db"
export LP_AUTH_SECRET_KEY="cb53bd28ffc37f3f99bcae7b2f23252fc74fe233f623c37b4fbce541c0c672d3"
export LP_REDIS_URL="redis://:redis_secure_pass_456@127.0.0.1:6379/0"

echo "✅ Environment variables exported"
echo "Now run: python fixed_auth_check.py"
