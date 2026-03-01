---
name: virtualmin
description: Virtualmin Remote API CLI for agents. Manage virtual servers, databases, SSL certificates, backups, PHP versions, and system configuration via HTTP basic auth. Provides convenience wrappers for common operations and a passthrough for all ~90 API endpoints. All output is JSON to stdout; status/errors to stderr.
---

# Virtualmin

Manage Virtualmin servers via the Remote API (`remote.cgi` on port 10000). Provides a `run` passthrough for any of the ~90 API programs plus convenience wrappers for domains, databases, SSL, backups, PHP, and system commands. Uses HTTP basic auth with master admin credentials. All output is JSON to stdout; status/errors to stderr.

## Usage

```bash
VM="uv run ~/.claude/skills/virtualmin/scripts/virtualmin.py"
```

## Commands

### Register a server

```bash
$VM server add prod --host vps1.example.com --user root --pass 'secretpass' --port 10000
$VM server add staging --host 192.168.1.10 --user root --pass 'pass123' --name "Staging" --no-verify
```

Password can also be set via `VM_PASSWORD` env var instead of `--pass`.

### Remove / list servers

```bash
$VM server remove prod
$VM server list
```

`server list` masks passwords in output. Credentials stored at `~/.claude/skills/virtualmin/data/servers.json` (chmod 600).

### Run any API program (passthrough)

```bash
$VM run prod list-domains -- --toplevel --name-only
$VM run prod list-plans
$VM run prod create-domain -- --domain new.example.com --pass secret --features-from-plan
$VM run prod modify-web -- --domain example.com --mode cgi
```

Sends `program=<name>&json=1` plus any extra params via POST to `remote.cgi`. Supports all ~90 Virtualmin API programs.

### Domains (Virtual Servers)

```bash
# List domains
$VM domains prod list
$VM domains prod list --toplevel --name-only
$VM domains prod list --user admin --with-feature ssl

# Detailed info for one domain
$VM domains prod info --domain example.com

# Create a virtual server
$VM domains prod create --domain new.example.com --pass 'secret'
$VM domains prod create --domain new.example.com --pass 'secret' --plan "Default Plan" --features-from-plan

# Delete a virtual server
$VM domains prod delete --domain old.example.com

# Enable / disable
$VM domains prod enable --domain example.com
$VM domains prod disable --domain example.com --why "Maintenance"

# Modify (all modify-domain flags via extra params)
$VM domains prod modify --domain example.com -- --newdomain renamed.example.com
$VM domains prod modify --domain example.com -- --quota 1024 --bw-limit 10240

# Validate configuration
$VM domains prod validate --domain example.com
$VM domains prod validate --all-domains
```

### Databases

```bash
# List databases for a domain
$VM db prod list --domain example.com
$VM db prod list --domain example.com --type mysql

# Create a database
$VM db prod create --domain example.com --name mydb --type mysql

# Delete a database
$VM db prod delete --domain example.com --name mydb --type mysql
```

### SSL Certificates

```bash
# List certs for a domain
$VM ssl prod list --domain example.com

# Check expiry dates
$VM ssl prod expiry --domain example.com
$VM ssl prod expiry --all-domains

# Generate / renew Let's Encrypt cert
$VM ssl prod letsencrypt --domain example.com
$VM ssl prod letsencrypt --domain example.com --renew

# Install a certificate (paths via extra params)
$VM ssl prod install --domain example.com -- --cert /path/to/cert.pem --key /path/to/key.pem --ca /path/to/ca.pem
```

### Backup & Restore

```bash
# Create a backup
$VM backup prod create --domain example.com --dest /backup/example.tar.gz
$VM backup prod create --all-domains --dest /backup/all.tar.gz

# Restore from backup
$VM backup prod restore --domain example.com --source /backup/example.tar.gz

# List scheduled backups
$VM backup prod scheduled

# List backup encryption keys
$VM backup prod keys
```

### PHP

```bash
# List available PHP versions
$VM php prod versions

# List PHP directories for a domain
$VM php prod dirs --domain example.com

# Set PHP version for a directory
$VM php prod set-dir --domain example.com --dir /home/example/public_html --version 8.2
```

### System

```bash
$VM system prod info           # Server information
$VM system prod check          # Check Virtualmin configuration
$VM system prod restart        # Restart services
$VM system prod status         # List server statuses
$VM system prod features       # List available features
```

## Passthrough-Only API Programs

All of these are accessible via `$VM run <alias> <program> [-- params...]`:

**Domains**: clone-domain, migrate-domain, move-domain, rename-domain, syncmx-domain, transfer-domain, unalias-domain, unsub-domain, notify-domain, enable-feature, disable-feature, modify-web

**Databases**: disconnect-database, import-database, modify-database-hosts, modify-database-pass

**SSL**: generate-cert, install-service-cert

**Templates**: create-template, delete-template, get-template, modify-template, list-templates

**S3**: list-s3-buckets, list-s3-files, upload-s3-file, download-s3-file, delete-s3-file, create-s3-bucket, delete-s3-bucket

**GCS**: list-gcs-buckets, list-gcs-files

**Users / Passwords**: change-password, list-commands, run-api-command

**Logging / Monitoring**: get-logs, list-backup-logs, writelogs

**Configuration**: config-system, fix-permissions, get-command, get-ssl, list-mysql-servers, list-php-ini, list-ports, list-service-certs, list-shared-addresses, modify-php-ini, modify-scheduled-backup, set-global-feature, set-mysql-pass

**Other**: check-connectivity, delete-backup, list-plans, list-redirects, modify-limits, reset-feature, start-stop-script

**Excluded** (not implemented): DNS (modify-dns), Rackspace (all rs-* commands), mail/spam systems (modify-spam, modify-mail, resend-email)

## Data Storage

Server credentials are stored at `~/.claude/skills/virtualmin/data/servers.json` (chmod 600).

State files:

- `servers.json` — registered servers with alias, host, port, credentials, SSL verify preference

## Prerequisites

- **Virtualmin** with Remote API enabled (Webmin > Webmin Configuration > Remote API)
- Master admin credentials (root or full admin user)
- Network access to port 10000 (or custom port) from the agent host
- Python 3.10+ and `uv` for running the script

## Tips

- SSL verification is off by default (self-signed certs are common on Webmin port 10000)
- The `run` passthrough can call any API program — use it for endpoints without convenience wrappers
- Extra params after `--` support `--key value`, `--key=value`, and `--flag` (boolean) formats
- All API responses include a `status` field — the CLI checks it and exits non-zero on errors
- Use `--name-only` on `domains list` for quick enumeration in scripts
- Backup `--dest` supports local paths and remote URLs (S3, FTP) depending on server config
- Domain `modify` accepts all `modify-domain` flags via extra params — check Virtualmin docs for the full list
