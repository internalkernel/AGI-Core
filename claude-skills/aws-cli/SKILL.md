---
name: aws-cli
description: AWS CLI wrapper for agents. Manage AWS infrastructure across EC2, S3, RDS, CloudFront, Route 53, Lambda, SES, ACM, WAF, Backup, IAM, and ElastiCache via subprocess with profile management and convenience wrappers. Most output is JSON to stdout; S3 operations and passthrough may emit plain text. Status/errors to stderr.
---

# AWS CLI

Manage AWS infrastructure via the AWS CLI. Provides a passthrough for any AWS command plus convenience wrappers for 12 services: EC2, S3, RDS, CloudFront, Route 53, Lambda, SES, ACM, WAF, AWS Backup, IAM, and ElastiCache. Most output is JSON to stdout; S3 file operations (`cp`, `sync`, `rm`, `presign`) and `run` passthrough may emit plain text. Status/errors to stderr.

Most services default to us-west-2. ACM and WAF auto-override to us-east-1.

## Usage

```bash
AWS="uv run ~/.claude/skills/aws-cli/scripts/aws-cli.py"
```

## Commands

### Register a profile

```bash
$AWS profile add prod --aws-profile default --region us-west-2 --name "Production"
```

### Remove / list profiles

```bash
$AWS profile remove prod
$AWS profile list
```

### Run any AWS CLI command (passthrough)

```bash
$AWS run prod -- ec2 describe-vpcs
$AWS run prod -- sts get-caller-identity
$AWS run prod -- s3api get-bucket-policy --bucket my-bucket
```

Prepends `aws --profile X --region Y --output json`.

### EC2 (us-west-2)

```bash
$AWS ec2 prod instances                    # List all instances
$AWS ec2 prod instances --state running    # Filter by state
$AWS ec2 prod instance i-0abc123           # Describe instance
$AWS ec2 prod start i-0abc123             # Start instance
$AWS ec2 prod stop i-0abc123              # Stop instance
$AWS ec2 prod reboot i-0abc123            # Reboot instance
$AWS ec2 prod sg-list                     # List security groups
$AWS ec2 prod sg-rules sg-0abc123         # Show SG rules
```

### S3 (global)

```bash
$AWS s3 prod buckets                              # List buckets
$AWS s3 prod ls my-bucket --prefix backups/       # List objects
$AWS s3 prod cp file.txt s3://bucket/key          # Upload
$AWS s3 prod cp s3://bucket/key file.txt          # Download
$AWS s3 prod sync ./local s3://bucket/path --delete
$AWS s3 prod rm s3://bucket/key --recursive
$AWS s3 prod presign s3://bucket/key --expires 3600
```

### RDS (us-west-2)

```bash
$AWS rds prod instances                           # List DB instances
$AWS rds prod instance my-db                      # Describe DB
$AWS rds prod snapshots --db my-db                # List snapshots
$AWS rds prod create-snapshot my-db --name "pre-deploy"
```

### CloudFront

```bash
$AWS cf prod distributions                        # List distributions
$AWS cf prod distribution E1ABC123               # Describe distribution
$AWS cf prod invalidate E1ABC123 --paths "/*"    # Create invalidation
```

### Route 53

```bash
$AWS r53 prod zones                               # List hosted zones
$AWS r53 prod records Z1ABC123                    # List DNS records
```

### Lambda (us-west-2)

```bash
$AWS lambda prod functions                        # List functions
$AWS lambda prod function my-func                 # Describe function
$AWS lambda prod invoke my-func --payload '{"key":"val"}'
$AWS lambda prod logs my-func --limit 20          # Recent logs
```

### SES (us-west-2)

```bash
$AWS ses prod identities                          # List email identities
$AWS ses prod send --from a@x.com --to b@x.com --subject "Hi" --body "Hello"
$AWS ses prod stats                               # Account stats
```

### ACM (auto us-east-1)

```bash
$AWS acm prod certificates                        # List certificates
$AWS acm prod certificate arn:aws:acm:...         # Describe certificate
```

### WAF (auto us-east-1)

```bash
$AWS waf prod acls                                # List Web ACLs
$AWS waf prod acl my-acl-id                       # Describe Web ACL
$AWS waf prod rules my-acl-id                     # List rules
```

### AWS Backup

```bash
$AWS backup prod plans                            # List backup plans
$AWS backup prod jobs --state COMPLETED           # List jobs by state
$AWS backup prod recovery-points my-vault         # List recovery points
```

### IAM (global)

```bash
$AWS iam prod users                               # List users
$AWS iam prod roles                               # List roles
$AWS iam prod policies --scope Local              # List policies
$AWS iam prod user admin                          # Describe user
```

### ElastiCache (us-west-2)

```bash
$AWS elasticache prod clusters                    # List clusters
$AWS elasticache prod cluster my-cluster          # Describe cluster
```

## Data Storage

Profile data is stored at `~/.claude/skills/aws-cli/data/profiles.json`.

State files:

- `profiles.json` — registered profiles with alias, AWS CLI profile name, default region

## Prerequisites

- **AWS CLI v2** installed and configured (`aws` command available)
- Credentials configured via `~/.aws/credentials`, env vars, or instance roles
- The skill only stores which AWS CLI profile name to use — authentication is fully delegated to the AWS CLI credential chain

## Tips

- The `run` passthrough accepts any AWS CLI command after `--`
- ACM and WAF commands automatically use us-east-1 regardless of the profile's default region
- `--output json` is auto-appended to all commands
- All commands propagate the AWS CLI's exit codes for scripting
- EC2 `instances` extracts Name tags and flattens the response for readability
- RDS `create-snapshot` auto-generates a timestamp-based identifier if `--name` is omitted
- WAF commands use CLOUDFRONT scope by default (for CloudFront-associated WAFs)
