#!/bin/sh
set -e

# Only the API service runs migrations (RUN_MIGRATIONS=1 in compose);
# the RPC worker shares this image and must not race it.
if [ "$RUN_MIGRATIONS" = "1" ]; then
    python -m app.run_migrations
fi

exec "$@"
