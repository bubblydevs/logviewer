# Multi-Database Log Viewer Setup

This log viewer now supports serving multiple log paths from different MongoDB databases.

## Configuration

### Option 1: Single Database (Legacy Mode)

For a single database, use the `CONNECTION_URI` or `MONGO_URI` environment variable:

```env
CONNECTION_URI=mongodb+srv://user:pass@cluster.mongodb.net/database
LOG_URL_PREFIX=/logs
HOST=0.0.0.0
PORT=8000
```

Access logs at:
- `http://localhost:8000/logs/<key>` - View log
- `http://localhost:8000/logs/raw/<key>` - View raw log

### Option 2: Multiple Databases (New Mode)

To serve different log paths from different MongoDB databases, use the `DATABASE_MAPPING` environment variable:

```env
DATABASE_MAPPING=billow=mongodb+srv://billow_user:pass@billow_cluster.mongodb.net/db,police=mongodb+srv://police_user:pass@police_cluster.mongodb.net/db,fire=mongodb+srv://fire_user:pass@fire_cluster.mongodb.net/db,emas=mongodb+srv://emas_user:pass@emas_cluster.mongodb.net/db,nh=mongodb+srv://nh_user:pass@nh_cluster.mongodb.net/db

LOG_URL_PREFIX=/logs
HOST=0.0.0.0
PORT=8000
```

Format: `PATH=MONGO_URI,PATH=MONGO_URI,...`

## URL Patterns

### With Multiple Databases:

Access logs using the path parameter:

- `http://localhost:8000/logs/billow/<key>` - View Billow log
- `http://localhost:8000/logs/billow/raw/<key>` - View Billow raw log
- `http://localhost:8000/logs/police/<key>` - View Police log
- `http://localhost:8000/logs/police/raw/<key>` - View Police raw log
- `http://localhost:8000/logs/fire/<key>` - View Fire log
- `http://localhost:8000/logs/fire/raw/<key>` - View Fire raw log
- `http://localhost:8000/logs/emas/<key>` - View EMAS log
- `http://localhost:8000/logs/emas/raw/<key>` - View EMAS raw log
- `http://localhost:8000/logs/nh/<key>` - View NH log
- `http://localhost:8000/logs/nh/raw/<key>` - View NH raw log

## Environment Setup Example

Create a `.env` file in the project root:

```env
# Multi-database configuration
DATABASE_MAPPING=billow=mongodb+srv://discordbubbly:isALtRUmF8sBNEA4@cluster0.ra0kgcv.mongodb.net/,police=mongodb+srv://discordbubbly:h2OMKMVgLtjlagcE@nottinghamshirepolice.b65gq.mongodb.net/,fire=mongodb+srv://discordbubbly:7uPaN5VIfoXhvM6G@cluster0.umeqv.mongodb.net/,emas=mongodb+srv://discordbubbly:6KUA8ZrHdQ1Y10Fa@cluster0.ri7aj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0,nh=mongodb+srv://discordbubbly:9vawI7HMhxWo6Ge8@cluster0.asd9a.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0

# URL prefix for log access
LOG_URL_PREFIX=/logs

# Server configuration
HOST=0.0.0.0
PORT=8000

# Attachment proxy (optional)
USE_ATTACHMENT_PROXY=no
ATTACHMENT_PROXY_URL=https://cdn.discordapp.xyz
```

## Notes

- **Legacy mode takes precedence**: If both `CONNECTION_URI` and `DATABASE_MAPPING` are set, `CONNECTION_URI` is used.
- **All paths must exist**: If a request comes for `/logs/<path>/<key>` where `<path>` is not in `DATABASE_MAPPING`, a 404 error is returned.
- **MongoDB database must exist**: Each MongoDB URI should point to a valid MongoDB instance with a `modmail_bot` database and `logs` collection containing the log documents with a `key` field.
- **Connection pooling**: Each path gets its own connection pool for better resource management.
