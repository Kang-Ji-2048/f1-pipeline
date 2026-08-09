# Deploying the F1 Pipeline to AWS (EC2 + S3)

This runbook stands up the pipeline and dashboard on a single EC2 instance using
Docker Compose, and (optionally) exports processed data to S3. It is written so
the whole thing can be done in ~15 minutes.

> **Credentials:** you run every step in your own AWS account. Nothing here asks
> anyone else to enter your keys — set them as environment/instance-role
> credentials on the box, and boto3 picks them up.

## Architecture on AWS

```
                 ┌────────────────────── EC2 instance ──────────────────────┐
Ergast / OpenF1  │  docker compose:  db (Postgres) ── pipeline ── dashboard  │
     APIs  ─────▶│                                       │           :8501    │──▶ browser
                 │                                       └── export-s3 ───────┼──▶ S3 bucket
                 └───────────────────────────────────────────────────────────┘
```

## 1. Prerequisites

- An AWS account and the AWS console (or CLI).
- A key pair for SSH.
- (Optional, for S3 export) an S3 bucket in the same region.

## 2. Launch the EC2 instance

1. **EC2 → Launch instance.** Choose **Ubuntu Server 22.04 LTS**, size
   `t3.small` or larger (Postgres + Streamlit + build need ~2 GB RAM).
2. **Key pair:** select or create one.
3. **Network / security group:** allow inbound
   - TCP **22** (SSH) from your IP,
   - TCP **8501** (dashboard) from your IP.
4. **Advanced details → User data:** paste the contents of
   [`user-data.sh`](user-data.sh). Edit `REPO_URL` first if you forked the repo.
5. Launch.

The user-data script installs Docker, clones the repo, runs
`docker compose up -d --build`, initialises the schema, and ingests the current
season. First boot takes a few minutes (image build + ingest).

## 3. Verify

SSH in and check the stack:

```bash
ssh -i <key.pem> ubuntu@<instance-public-ip>
cd /opt/f1-pipeline
docker compose ps
docker compose logs -f dashboard
```

Then open `http://<instance-public-ip>:8501` in your browser — the dashboard
should render the three views against the ingested data.

## 4. (Optional) Export to S3

1. Give the instance access to S3, **either**:
   - attach an **IAM instance role** with `s3:PutObject` on your bucket (preferred), **or**
   - set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` in `.env`.
2. Set `S3_BUCKET` (and optionally `S3_PREFIX`) in `/opt/f1-pipeline/.env`.
3. Run the export:

```bash
docker compose run --rm \
  -e S3_BUCKET -e S3_PREFIX \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
  pipeline export-s3 --season 2025
```

Objects land at `s3://<bucket>/<prefix>/2025/<table>.csv`.

## 5. Updating a running instance

To deploy the latest code after merging changes, SSH in and run the update
script from the repo root:

```bash
cd /opt/f1-pipeline
sudo bash deploy/update.sh              # pulls latest, rebuilds, force-recreates
```

It fetches the current branch (override with `BRANCH=<name>`), rebuilds the
images and **force-recreates** the containers (a plain `--build` keeps the old
container running, so the dashboard would otherwise still show the stale
version). Pass `--migrate` to also apply Alembic migrations — but only on an
Alembic-managed database (instances first brought up with `init-db` are not
stamped; see the note in [`update.sh`](update.sh)). Your Postgres volume, and so
the ingested data, is left untouched.

After it finishes, hard-refresh the dashboard (or use **⋮ → Clear cache**) since
Streamlit caches aggressively.

## 6. Keeping data fresh

Schedule ingestion with cron on the instance:

```bash
# crontab -e  — ingest the current season every Monday 06:00
0 6 * * 1 cd /opt/f1-pipeline && docker compose run --rm pipeline ingest-all --season $(date +\%Y)
```

For live sessions, run the real-time poller:

```bash
docker compose run --rm pipeline live --session-key latest --interval 5
```

## 7. Stable address & HTTPS (optional)

By default the dashboard is at `http://<public-ip>:8501`, and the public IP
changes whenever the instance is stopped/started. To make it stable and secure:

**Stable IP — allocate an Elastic IP:**
1. EC2 → **Elastic IPs** → **Allocate Elastic IP address** → Allocate.
2. Select it → **Actions → Associate** → choose your instance → Associate.

The instance now keeps that IP across stop/start. (Note: an Elastic IP that is
*not* associated with a running instance incurs a small hourly charge.)

**HTTPS — front the dashboard with a reverse proxy.** Streamlit does not
terminate TLS itself. The simplest route is a small reverse proxy (e.g. Caddy or
nginx) on the instance that proxies `:443` → `:8501` and obtains a certificate.
This needs a **domain name** pointed at the Elastic IP; with a domain, Caddy can
auto-provision a Let's Encrypt certificate:

```bash
# on the instance, with a domain (dash.example.com) pointed at the Elastic IP
sudo apt-get install -y caddy
echo "dash.example.com {
    reverse_proxy localhost:8501
}" | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
# then open the 443 inbound rule in the security group and browse https://dash.example.com
```

Without a domain, keep the `http://<ip>:8501` setup and restrict the 8501
security-group rule to your own IP.

## 8. Teardown

```bash
docker compose down -v   # stop stack and remove the Postgres volume
```

Then terminate the EC2 instance (and empty/delete the S3 bucket if you made one)
from the console to stop incurring charges.
