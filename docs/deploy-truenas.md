# Deploying RuneChat on TrueNAS SCALE

Use the maintained deployment bundle in [`deploy/`](../deploy/).

Fast path:

```bash
git clone https://github.com/MoonRuneInc/RuneChat.git
cd RuneChat/deploy
./truenas.sh init
# edit .env.prod and fill DATABASE_URL
./truenas.sh up-build
```

For pre-built image tarballs, put `runechat-app.tar` and `runechat-frontend.tar` in `deploy/`, then run:

```bash
./truenas.sh up
```

The script validates Docker Compose, starts the stack, and waits for `http://localhost:8080/health`.

See [`deploy/README.md`](../deploy/README.md) for Cloudflare Tunnel, existing reverse proxy, Custom App, rollback, and troubleshooting steps.
