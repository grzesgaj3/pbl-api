# Deployment guide (VPS)

Target: a small Linux VPS (1 vCPU / 1 GB RAM is enough) running MariaDB and the
API behind nginx with TLS. Commands assume Debian/Ubuntu; on Arch replace
`apt install` with `pacman -S` and the service paths stay the same.

Result: the API uses one worker, a two-connection pool and a hard 256 MB memory
cap, while MariaDB is tuned to stay under ~200 MB.

---

## 1. System packages and a service user

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip mariadb-server nginx git
sudo adduser --system --group --home /opt/pbl-api --shell /usr/sbin/nologin pbl
```

## 2. Database

Create the database and a dedicated user:

```bash
sudo mariadb -e "
CREATE DATABASE pbl CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pbl'@'localhost' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON pbl.* TO 'pbl'@'localhost';
FLUSH PRIVILEGES;"
```

Harden the server (`sudo mariadb-secure-installation`) and, on a small VPS,
shrink its memory use — add to `/etc/mysql/mariadb.conf.d/50-server.cnf` under
`[mysqld]`:

```ini
innodb_buffer_pool_size = 128M
performance_schema      = OFF
skip_name_resolve       = ON
max_connections         = 30
```

```bash
sudo systemctl restart mariadb
```

`performance_schema = OFF` alone frees 100–200 MB on default installs.

## 3. Deploy the code

```bash
sudo -u pbl git clone <repo-url> /opt/pbl-api
cd /opt/pbl-api
sudo -u pbl python3 -m venv .venv
sudo -u pbl .venv/bin/pip install --upgrade pip
sudo -u pbl .venv/bin/pip install -r requirements.txt
```

## 4. Configure the environment

`app/core/config.py` reads `.env` from the project root, so it works regardless
of the working directory.

```bash
sudo -u pbl cp /opt/pbl-api/.env.example /opt/pbl-api/.env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # admin key
sudo -u pbl nano /opt/pbl-api/.env
```

Set at minimum:

```dotenv
DATABASE_URL=mysql+pymysql://pbl:CHANGE_ME_STRONG_PASSWORD@localhost:3306/pbl?charset=utf8mb4
ADMIN_API_KEY=<the generated key>
ENABLE_DOCS=false
```

Restrict the file — it holds the admin key:

```bash
sudo chown pbl:pbl /opt/pbl-api/.env
sudo chmod 600 /opt/pbl-api/.env
```

## 5. Create the schema and a first bridge

```bash
cd /opt/pbl-api
sudo -u pbl .venv/bin/alembic upgrade head
sudo -u pbl .venv/bin/python -m app.scripts.create_bridge mostek1
```

Copy the printed bridge key somewhere safe; it is not stored in plaintext.

## 6. Run the API as a service

The unit in [`deploy/pbl-api.service`](../deploy/pbl-api.service) pins the
process to one worker and caps its memory.

```bash
sudo cp /opt/pbl-api/deploy/pbl-api.service /etc/systemd/system/pbl-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now pbl-api
systemctl status pbl-api --no-pager
curl -s http://127.0.0.1:8000/health/ready
# {"status":"ok","version":"1.0.0"}
```

## 7. Reverse proxy and TLS

```bash
sudo cp /opt/pbl-api/deploy/nginx-pbl-api.conf /etc/nginx/sites-available/pbl-api
sudo ln -s /etc/nginx/sites-available/pbl-api /etc/nginx/sites-enabled/pbl-api
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pbl.example.com
```

Open the firewall to HTTP/HTTPS only; the API port stays on loopback.

```bash
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

---

## Keeping memory small

| Layer | Setting | Effect |
|-------|---------|--------|
| API | `--workers 1` | One process instead of per-core duplication. |
| API | `DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=3` | At most 5 connections per worker. |
| API | `MemoryMax=256M` in the unit | The kernel kills a runaway process instead of the VPS. |
| API | `--limit-max-requests 100000` | Periodic worker recycle bounds slow growth. |
| API | `ENABLE_DOCS=false` | Skips building/serving the OpenAPI schema. |
| MariaDB | `innodb_buffer_pool_size=128M`, `performance_schema=OFF` | The largest single saving. |

Check the real numbers after a day of traffic:

```bash
systemctl show pbl-api -p MemoryCurrent
sudo mariadb -e "SHOW GLOBAL STATUS LIKE 'Threads_connected';"
```

## Logs and rotation

The API logs to stdout/stderr, which journald collects. Cap the journal so it
cannot fill the disk (`/etc/systemd/journald.conf`):

```ini
SystemMaxUse=200M
```

```bash
journalctl -u pbl-api -f
```

Nginx keeps its own logs; let `logrotate` handle them (it is configured by
default on Debian/Ubuntu).

## Backups

A nightly logical dump is enough for this data volume:

```bash
sudo -u pbl crontab -e
```

```cron
15 3 * * * mariadb-dump --single-transaction pbl | gzip > /opt/pbl-api/backup/pbl-$(date +\%F).sql.gz
30 3 * * * find /opt/pbl-api/backup -name 'pbl-*.sql.gz' -mtime +14 -delete
```

```bash
sudo -u pbl mkdir -p /opt/pbl-api/backup
```

Restore with `zcat file.sql.gz | mariadb pbl`.

## Upgrading

```bash
cd /opt/pbl-api
sudo -u pbl git pull
sudo -u pbl .venv/bin/pip install -r requirements.txt
sudo -u pbl .venv/bin/alembic upgrade head
sudo systemctl restart pbl-api
curl -s http://127.0.0.1:8000/health/ready
```

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `/health/ready` → `503` | Database unreachable: check `DATABASE_URL`, MariaDB status, credentials. |
| `Access denied for user` | Password or host in `DATABASE_URL`; grant must include `'pbl'@'localhost'`. |
| Every request → `403` | Bridge key rotated/deactivated, or `ADMIN_API_KEY` mismatch. |
| `502 Bad Gateway` | The API service is down; check `journalctl -u pbl-api`. |
| Service killed after a burst | `MemoryMax` reached — lower `DB_POOL_SIZE` or raise the cap. |
| Times are shifted by hours | The MariaDB session time zone is not UTC; the app sets `time_zone='+00:00'` itself, so check for a proxy/DB override. |
