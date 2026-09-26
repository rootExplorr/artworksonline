# VM deployment

1. Point the domain's DNS A record to the VM public IP. In the Azure network security group, allow inbound TCP 80 and 443; restrict SSH (22) to your IP. Do not open ports 3306, 8000, or 4200.
2. Install Docker Engine and the Docker Compose plugin on Ubuntu, then clone this repository to `/opt/artonline` on the VM. For a private GitHub repository, configure a read-only deploy key for cloning.
3. From `deploy/`, copy `.env.example` to `.env`. Set `SITE_ADDRESS` and `FRONTEND_ORIGIN` to your domain, generate unique database passwords using alphanumeric characters, generate an Argon2 admin password hash and a random `AUTH_SECRET_KEY` of at least 32 characters. Keep `AUTH_COOKIE_SECURE=true` when using HTTPS. Put the Argon2 value in single quotes in `.env` because it contains `$` characters. Never commit `.env`.
4. Start the services from `deploy/`:

   ```bash
   docker compose --env-file .env up -d --build
   docker compose ps
   docker compose logs -f
   ```

5. Visit `https://<your-domain>`. Caddy obtains and renews the TLS certificate automatically once DNS points to the VM and ports 80/443 are reachable.

For temporary IP-only testing, set `SITE_ADDRESS=http://<vm-ip>`, `FRONTEND_ORIGIN=http://<vm-ip>`, and `AUTH_COOKIE_SECURE=false`, then run `docker compose --env-file .env up -d`. Visit `http://<vm-ip>` only. HTTP is unencrypted: do not log in or submit passwords until HTTPS is configured. Restore the HTTPS settings when the domain works.

MySQL data, uploaded images, and Caddy certificates use named Docker volumes. Back them up regularly, especially `mysql_data` and `artwork_uploads`. This single-VM setup has no automatic failover.

## GitHub Actions deployment

The workflow deploys on pushes to `main`. Add these repository Actions secrets: `VM_HOST` (public IP or hostname), `VM_USER`, `VM_SSH_KEY` (private key authorized for that VM user), `VM_KNOWN_HOSTS` (verified SSH host key line), and `SITE_URL` (for example `https://art.example.com`). The VM user must be able to run Docker. The repository must already be cloned at `/opt/artonline`, and `deploy/.env` must be configured there.