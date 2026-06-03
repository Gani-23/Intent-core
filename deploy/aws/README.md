# AWS EC2 backend hardening

No domain is required.

## Shape

- one Ubuntu EC2 instance
- Docker + Docker Compose
- bundled Postgres container
- API on port `8000`
- worker as separate container

## Bootstrap

Run as root:

```bash
bash deploy/aws/bootstrap_ubuntu_docker.sh
```

Then log out and back in if you want Docker group access as `ubuntu`.

## Deploy

```bash
cp docker/control.aws.env.example docker/control.aws.env
```

Edit:

- `LSA_API_KEY`
- `POSTGRES_PASSWORD`
- optional org/env names

Deploy:

```bash
bash deploy/aws/deploy_control_plane.sh
```

Check:

```bash
curl http://127.0.0.1:8000/health
docker compose --profile postgres --env-file docker/control.aws.env -f docker/compose.control.yml ps
```

## Hardening validation

Run:

```bash
bash deploy/aws/run_hardening_validation.sh
```

This runs:

- operational validation
- deployment readiness
- observability export

## Auto-start on reboot

Copy:

```bash
sudo cp deploy/aws/lsa-control-plane.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lsa-control-plane
```

## Public access

Without a domain, use:

- `http://EC2_PUBLIC_IP:8000/health`
- `http://EC2_PUBLIC_IP:8000/ops`

Restrict security-group access instead of exposing broadly.
