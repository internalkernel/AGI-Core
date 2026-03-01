# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""AWS CLI wrapper for agents. Runs AWS commands via subprocess.

Usage:
    uv run aws-cli.py <command> [options]

Requires AWS CLI installed and configured (~/.aws/credentials or env vars).
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# --- Services that must use us-east-1 ---
US_EAST_1_PREFIXES = ("acm", "wafv2", "waf", "shield")


def get_data_dir() -> Path:
    workspace = os.environ.get("OPENCLAW_WORKSPACE")
    if workspace:
        d = Path(workspace) / "cache" / "aws-cli"
    else:
        d = Path.home() / ".openclaw" / "skills" / "aws-cli" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_profiles() -> dict:
    path = get_data_dir() / "profiles.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_profiles(profiles: dict):
    path = get_data_dir() / "profiles.json"
    path.write_text(json.dumps(profiles, indent=2) + "\n")


def get_profile(alias: str) -> dict:
    profiles = load_profiles()
    if alias not in profiles:
        stderr(f"Profile '{alias}' not found. Use 'profile list' to see registered profiles.")
        sys.exit(1)
    return profiles[alias]


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def out_json(data):
    print(json.dumps(data, indent=2, default=str))


# --- AWS core ---


def run_aws(profile_alias: str, args: list[str], region_override: str | None = None) -> dict | list | str:
    """Run an AWS CLI command with profile/region from config."""
    profile = get_profile(profile_alias)

    region = region_override or profile.get("region", "us-west-2")

    # Auto-override region for ACM / WAF / Shield
    if args and any(args[0].startswith(p) for p in US_EAST_1_PREFIXES):
        region = "us-east-1"

    cmd = [
        "aws",
        "--profile", profile.get("aws_profile", "default"),
        "--region", region,
        "--output", "json",
    ] + args

    # Redact all flag values by default; only show values for safe display flags
    SAFE_DISPLAY_FLAGS = {
        "--profile", "--region", "--output", "--query",
        "--max-items", "--page-size", "--starting-token",
        "--no-paginate", "--filter", "--filters",
        "--instance-ids", "--stack-name", "--table-name",
        "--bucket", "--key", "--prefix", "--delimiter",
        "--function-name", "--cluster", "--service",
    }
    display_cmd = []
    skip_next = False
    redact_next = False
    for i, a in enumerate(cmd):
        if skip_next:
            display_cmd.append(a)
            skip_next = False
        elif redact_next:
            display_cmd.append("****")
            redact_next = False
        elif a.startswith("--") and "=" in a:
            # Handle --flag=value form
            flag_part = a.split("=", 1)[0]
            if flag_part.lower() in SAFE_DISPLAY_FLAGS:
                display_cmd.append(a)
            else:
                display_cmd.append(f"{flag_part}=****")
        elif a.startswith("--"):
            display_cmd.append(a)
            if a.lower() in SAFE_DISPLAY_FLAGS:
                skip_next = True
            else:
                redact_next = True
        else:
            display_cmd.append(a)
    stderr(f"$ {' '.join(display_cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        stderr("Error: 'aws' command not found. Ensure AWS CLI is installed.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        stderr("Error: Command timed out after 120 seconds.")
        sys.exit(1)

    if result.returncode != 0:
        stderr(f"AWS CLI error (exit {result.returncode}):")
        if result.stderr:
            stderr(result.stderr.strip())
        sys.exit(result.returncode)

    output = result.stdout.strip()
    if not output:
        return {"ok": True}

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return output


# --- Profile management ---


def cmd_profile_add(args):
    profiles = load_profiles()
    if args.alias in profiles:
        stderr(f"Profile '{args.alias}' already exists. Remove it first.")
        sys.exit(1)

    profiles[args.alias] = {
        "name": args.name or args.alias,
        "aws_profile": args.aws_profile,
        "region": args.region,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    save_profiles(profiles)
    stderr(f"Added profile '{args.alias}' (aws_profile={args.aws_profile}, region={args.region})")


def cmd_profile_remove(args):
    profiles = load_profiles()
    if args.alias not in profiles:
        stderr(f"Profile '{args.alias}' not found.")
        sys.exit(1)
    name = profiles[args.alias].get("name", args.alias)
    del profiles[args.alias]
    save_profiles(profiles)
    stderr(f"Removed profile '{args.alias}' ({name})")


def cmd_profile_list(args):
    profiles = load_profiles()
    result = []
    for alias, info in profiles.items():
        result.append({
            "alias": alias,
            "name": info.get("name", alias),
            "aws_profile": info.get("aws_profile"),
            "region": info.get("region"),
            "added": info.get("added"),
        })
    out_json(result)


# --- Passthrough ---


def cmd_run(args):
    aws_args = args.aws_args
    if aws_args and aws_args[0] == "--":
        aws_args = aws_args[1:]
    output = run_aws(args.alias, aws_args)
    if isinstance(output, str):
        print(output)
    else:
        out_json(output)


# --- EC2 ---


def cmd_ec2(args):
    action = args.ec2_action

    if action == "instances":
        filters = []
        if args.state and args.state != "all":
            filters = ["--filters", f"Name=instance-state-name,Values={args.state}"]
        data = run_aws(args.alias, ["ec2", "describe-instances"] + filters)
        instances = []
        for res in data.get("Reservations", []):
            for inst in res.get("Instances", []):
                name = ""
                for tag in inst.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                instances.append({
                    "InstanceId": inst.get("InstanceId"),
                    "Name": name,
                    "State": inst.get("State", {}).get("Name"),
                    "Type": inst.get("InstanceType"),
                    "PublicIp": inst.get("PublicIpAddress", ""),
                    "PrivateIp": inst.get("PrivateIpAddress", ""),
                    "LaunchTime": inst.get("LaunchTime"),
                })
        out_json(instances)

    elif action == "instance":
        data = run_aws(args.alias, ["ec2", "describe-instances", "--instance-ids", args.id])
        out_json(data)

    elif action == "start":
        data = run_aws(args.alias, ["ec2", "start-instances", "--instance-ids", args.id])
        out_json(data)
        stderr(f"Starting instance {args.id}")

    elif action == "stop":
        data = run_aws(args.alias, ["ec2", "stop-instances", "--instance-ids", args.id])
        out_json(data)
        stderr(f"Stopping instance {args.id}")

    elif action == "reboot":
        data = run_aws(args.alias, ["ec2", "reboot-instances", "--instance-ids", args.id])
        out_json(data)
        stderr(f"Rebooting instance {args.id}")

    elif action == "sg-list":
        data = run_aws(args.alias, ["ec2", "describe-security-groups"])
        groups = []
        for sg in data.get("SecurityGroups", []):
            groups.append({
                "GroupId": sg.get("GroupId"),
                "GroupName": sg.get("GroupName"),
                "Description": sg.get("Description"),
                "VpcId": sg.get("VpcId"),
            })
        out_json(groups)

    elif action == "sg-rules":
        data = run_aws(args.alias, ["ec2", "describe-security-groups", "--group-ids", args.sg_id])
        sg = data.get("SecurityGroups", [{}])[0]
        out_json({
            "GroupId": sg.get("GroupId"),
            "GroupName": sg.get("GroupName"),
            "InboundRules": sg.get("IpPermissions", []),
            "OutboundRules": sg.get("IpPermissionsEgress", []),
        })


# --- S3 ---


def cmd_s3(args):
    action = args.s3_action

    if action == "buckets":
        data = run_aws(args.alias, ["s3api", "list-buckets"])
        out_json(data.get("Buckets", []) if isinstance(data, dict) else data)

    elif action == "ls":
        s3_args = ["s3", "ls", f"s3://{args.bucket}"]
        if args.prefix:
            s3_args[-1] += f"/{args.prefix}"
        s3_args.append("--recursive")
        output = run_aws(args.alias, s3_args)
        if isinstance(output, str):
            print(output)
        else:
            out_json(output)

    elif action == "cp":
        cp_args = ["s3", "cp", args.src, args.dst]
        output = run_aws(args.alias, cp_args)
        if isinstance(output, str):
            print(output)
        else:
            out_json(output)

    elif action == "sync":
        sync_args = ["s3", "sync", args.src, args.dst]
        if args.delete:
            sync_args.append("--delete")
        output = run_aws(args.alias, sync_args)
        if isinstance(output, str):
            print(output)
        else:
            out_json(output)

    elif action == "rm":
        rm_args = ["s3", "rm", args.path]
        if args.recursive:
            rm_args.append("--recursive")
        output = run_aws(args.alias, rm_args)
        if isinstance(output, str):
            print(output)
        else:
            out_json(output)

    elif action == "presign":
        presign_args = ["s3", "presign", args.s3_url, "--expires-in", str(args.expires)]
        output = run_aws(args.alias, presign_args)
        if isinstance(output, str):
            print(output)
        else:
            out_json(output)


# --- RDS ---


def cmd_rds(args):
    action = args.rds_action

    if action == "instances":
        data = run_aws(args.alias, ["rds", "describe-db-instances"])
        instances = []
        for db in data.get("DBInstances", []):
            instances.append({
                "DBInstanceIdentifier": db.get("DBInstanceIdentifier"),
                "Engine": db.get("Engine"),
                "EngineVersion": db.get("EngineVersion"),
                "DBInstanceClass": db.get("DBInstanceClass"),
                "Status": db.get("DBInstanceStatus"),
                "Endpoint": db.get("Endpoint", {}).get("Address", ""),
                "MultiAZ": db.get("MultiAZ"),
                "StorageType": db.get("StorageType"),
                "AllocatedStorage": db.get("AllocatedStorage"),
            })
        out_json(instances)

    elif action == "instance":
        data = run_aws(args.alias, ["rds", "describe-db-instances", "--db-instance-identifier", args.id])
        out_json(data)

    elif action == "snapshots":
        snap_args = ["rds", "describe-db-snapshots"]
        if args.db:
            snap_args.extend(["--db-instance-identifier", args.db])
        data = run_aws(args.alias, snap_args)
        snapshots = []
        for s in data.get("DBSnapshots", []):
            snapshots.append({
                "DBSnapshotIdentifier": s.get("DBSnapshotIdentifier"),
                "DBInstanceIdentifier": s.get("DBInstanceIdentifier"),
                "Status": s.get("Status"),
                "SnapshotCreateTime": s.get("SnapshotCreateTime"),
                "Engine": s.get("Engine"),
                "AllocatedStorage": s.get("AllocatedStorage"),
                "SnapshotType": s.get("SnapshotType"),
            })
        out_json(snapshots)

    elif action == "create-snapshot":
        snap_id = args.name or f"{args.id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        data = run_aws(args.alias, [
            "rds", "create-db-snapshot",
            "--db-instance-identifier", args.id,
            "--db-snapshot-identifier", snap_id,
        ])
        out_json(data)
        stderr(f"Creating snapshot '{snap_id}' for {args.id}")


# --- CloudFront ---


def cmd_cf(args):
    action = args.cf_action

    if action == "distributions":
        data = run_aws(args.alias, ["cloudfront", "list-distributions"])
        dists = []
        for d in data.get("DistributionList", {}).get("Items", []):
            dists.append({
                "Id": d.get("Id"),
                "DomainName": d.get("DomainName"),
                "Status": d.get("Status"),
                "Enabled": d.get("Enabled"),
                "Aliases": d.get("Aliases", {}).get("Items", []),
                "Origins": [o.get("DomainName") for o in d.get("Origins", {}).get("Items", [])],
            })
        out_json(dists)

    elif action == "distribution":
        data = run_aws(args.alias, ["cloudfront", "get-distribution", "--id", args.id])
        out_json(data)

    elif action == "invalidate":
        data = run_aws(args.alias, [
            "cloudfront", "create-invalidation",
            "--distribution-id", args.id,
            "--paths", args.paths,
        ])
        out_json(data)
        stderr(f"Invalidation created for {args.id}: {args.paths}")


# --- Route 53 ---


def cmd_r53(args):
    action = args.r53_action

    if action == "zones":
        data = run_aws(args.alias, ["route53", "list-hosted-zones"])
        zones = []
        for z in data.get("HostedZones", []):
            zones.append({
                "Id": z.get("Id"),
                "Name": z.get("Name"),
                "RecordCount": z.get("ResourceRecordSetCount"),
                "Private": z.get("Config", {}).get("PrivateZone"),
            })
        out_json(zones)

    elif action == "records":
        data = run_aws(args.alias, ["route53", "list-resource-record-sets", "--hosted-zone-id", args.zone_id])
        out_json(data.get("ResourceRecordSets", []) if isinstance(data, dict) else data)


# --- Lambda ---


def cmd_lambda(args):
    action = args.lambda_action

    if action == "functions":
        data = run_aws(args.alias, ["lambda", "list-functions"])
        funcs = []
        for f in data.get("Functions", []):
            funcs.append({
                "FunctionName": f.get("FunctionName"),
                "Runtime": f.get("Runtime"),
                "MemorySize": f.get("MemorySize"),
                "Timeout": f.get("Timeout"),
                "LastModified": f.get("LastModified"),
                "CodeSize": f.get("CodeSize"),
            })
        out_json(funcs)

    elif action == "function":
        data = run_aws(args.alias, ["lambda", "get-function", "--function-name", args.name])
        out_json(data)

    elif action == "invoke":
        invoke_args = [
            "lambda", "invoke",
            "--function-name", args.name,
            "--cli-binary-format", "raw-in-base64-out",
            "/dev/stdout",
        ]
        if args.payload:
            invoke_args.extend(["--payload", args.payload])
        data = run_aws(args.alias, invoke_args)
        if isinstance(data, str):
            print(data)
        else:
            out_json(data)

    elif action == "logs":
        limit = str(args.limit or 20)
        log_group = f"/aws/lambda/{args.name}"
        data = run_aws(args.alias, [
            "logs", "filter-log-events",
            "--log-group-name", log_group,
            "--limit", limit,
            "--interleaved",
        ])
        events = data.get("events", []) if isinstance(data, dict) else data
        out_json(events)


# --- SES ---


def cmd_ses(args):
    action = args.ses_action

    if action == "identities":
        data = run_aws(args.alias, ["sesv2", "list-email-identities"])
        out_json(data.get("EmailIdentities", []) if isinstance(data, dict) else data)

    elif action == "send":
        data = run_aws(args.alias, [
            "sesv2", "send-email",
            "--from-email-address", args.from_addr,
            "--destination", json.dumps({"ToAddresses": [args.to_addr]}),
            "--content", json.dumps({
                "Simple": {
                    "Subject": {"Data": args.subject},
                    "Body": {"Text": {"Data": args.body}},
                }
            }),
        ])
        out_json(data)
        stderr(f"Email sent from {args.from_addr} to {args.to_addr}")

    elif action == "stats":
        data = run_aws(args.alias, ["sesv2", "get-account"])
        out_json(data)


# --- ACM (auto us-east-1) ---


def cmd_acm(args):
    action = args.acm_action

    if action == "certificates":
        data = run_aws(args.alias, ["acm", "list-certificates"])
        certs = []
        for c in data.get("CertificateSummaryList", []):
            certs.append({
                "CertificateArn": c.get("CertificateArn"),
                "DomainName": c.get("DomainName"),
                "Status": c.get("Status"),
                "Type": c.get("Type"),
                "InUse": c.get("InUseBy", []) != [],
            })
        out_json(certs)

    elif action == "certificate":
        data = run_aws(args.alias, ["acm", "describe-certificate", "--certificate-arn", args.arn])
        out_json(data)


# --- WAF (auto us-east-1) ---


def cmd_waf(args):
    action = args.waf_action

    if action == "acls":
        data = run_aws(args.alias, ["wafv2", "list-web-acls", "--scope", "CLOUDFRONT"])
        out_json(data.get("WebACLs", []) if isinstance(data, dict) else data)

    elif action == "acl":
        # Need to list first to get ARN from name, or user passes ID that is actually Name
        data = run_aws(args.alias, [
            "wafv2", "list-web-acls", "--scope", "CLOUDFRONT",
        ])
        acls = data.get("WebACLs", []) if isinstance(data, dict) else []
        target = None
        for acl in acls:
            if acl.get("Id") == args.id or acl.get("Name") == args.id:
                target = acl
                break
        if not target:
            stderr(f"Web ACL '{args.id}' not found.")
            sys.exit(1)
        detail = run_aws(args.alias, [
            "wafv2", "get-web-acl",
            "--scope", "CLOUDFRONT",
            "--name", target["Name"],
            "--id", target["Id"],
        ])
        out_json(detail)

    elif action == "rules":
        data = run_aws(args.alias, [
            "wafv2", "list-web-acls", "--scope", "CLOUDFRONT",
        ])
        acls = data.get("WebACLs", []) if isinstance(data, dict) else []
        target = None
        for acl in acls:
            if acl.get("Id") == args.acl_id or acl.get("Name") == args.acl_id:
                target = acl
                break
        if not target:
            stderr(f"Web ACL '{args.acl_id}' not found.")
            sys.exit(1)
        detail = run_aws(args.alias, [
            "wafv2", "get-web-acl",
            "--scope", "CLOUDFRONT",
            "--name", target["Name"],
            "--id", target["Id"],
        ])
        rules = detail.get("WebACL", {}).get("Rules", []) if isinstance(detail, dict) else detail
        out_json(rules)


# --- AWS Backup ---


def cmd_backup(args):
    action = args.backup_action

    if action == "plans":
        data = run_aws(args.alias, ["backup", "list-backup-plans"])
        plans = []
        for p in data.get("BackupPlansList", []):
            plans.append({
                "BackupPlanId": p.get("BackupPlanId"),
                "BackupPlanName": p.get("BackupPlanName"),
                "CreationDate": p.get("CreationDate"),
                "LastExecutionDate": p.get("LastExecutionDate"),
            })
        out_json(plans)

    elif action == "jobs":
        job_args = ["backup", "list-backup-jobs"]
        if args.state:
            job_args.extend(["--by-state", args.state])
        data = run_aws(args.alias, job_args)
        jobs = []
        for j in data.get("BackupJobs", []):
            jobs.append({
                "BackupJobId": j.get("BackupJobId"),
                "ResourceArn": j.get("ResourceArn"),
                "ResourceType": j.get("ResourceType"),
                "State": j.get("State"),
                "CreationDate": j.get("CreationDate"),
                "CompletionDate": j.get("CompletionDate"),
                "BackupSizeBytes": j.get("BackupSizeInBytes"),
            })
        out_json(jobs)

    elif action == "recovery-points":
        data = run_aws(args.alias, [
            "backup", "list-recovery-points-by-backup-vault",
            "--backup-vault-name", args.vault_name,
        ])
        points = []
        for rp in data.get("RecoveryPoints", []):
            points.append({
                "RecoveryPointArn": rp.get("RecoveryPointArn"),
                "ResourceArn": rp.get("ResourceArn"),
                "ResourceType": rp.get("ResourceType"),
                "Status": rp.get("Status"),
                "CreationDate": rp.get("CreationDate"),
                "BackupSizeBytes": rp.get("BackupSizeBytes"),
            })
        out_json(points)


# --- IAM (global) ---


def cmd_iam(args):
    action = args.iam_action

    if action == "users":
        data = run_aws(args.alias, ["iam", "list-users"])
        users = []
        for u in data.get("Users", []):
            users.append({
                "UserName": u.get("UserName"),
                "UserId": u.get("UserId"),
                "Arn": u.get("Arn"),
                "CreateDate": u.get("CreateDate"),
                "PasswordLastUsed": u.get("PasswordLastUsed"),
            })
        out_json(users)

    elif action == "roles":
        data = run_aws(args.alias, ["iam", "list-roles"])
        roles = []
        for r in data.get("Roles", []):
            roles.append({
                "RoleName": r.get("RoleName"),
                "RoleId": r.get("RoleId"),
                "Arn": r.get("Arn"),
                "CreateDate": r.get("CreateDate"),
                "Description": r.get("Description", ""),
            })
        out_json(roles)

    elif action == "policies":
        pol_args = ["iam", "list-policies"]
        if args.scope:
            pol_args.extend(["--scope", args.scope])
        data = run_aws(args.alias, pol_args)
        policies = []
        for p in data.get("Policies", []):
            policies.append({
                "PolicyName": p.get("PolicyName"),
                "PolicyId": p.get("PolicyId"),
                "Arn": p.get("Arn"),
                "AttachmentCount": p.get("AttachmentCount"),
                "CreateDate": p.get("CreateDate"),
            })
        out_json(policies)

    elif action == "user":
        data = run_aws(args.alias, ["iam", "get-user", "--user-name", args.name])
        out_json(data)


# --- ElastiCache ---


def cmd_elasticache(args):
    action = args.elasticache_action

    if action == "clusters":
        data = run_aws(args.alias, ["elasticache", "describe-cache-clusters"])
        clusters = []
        for c in data.get("CacheClusters", []):
            clusters.append({
                "CacheClusterId": c.get("CacheClusterId"),
                "Engine": c.get("Engine"),
                "EngineVersion": c.get("EngineVersion"),
                "CacheNodeType": c.get("CacheNodeType"),
                "CacheClusterStatus": c.get("CacheClusterStatus"),
                "NumCacheNodes": c.get("NumCacheNodes"),
            })
        out_json(clusters)

    elif action == "cluster":
        data = run_aws(args.alias, [
            "elasticache", "describe-cache-clusters",
            "--cache-cluster-id", args.id,
            "--show-cache-node-info",
        ])
        out_json(data)


# --- Argument parser ---


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AWS CLI wrapper for agents")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- profile ---
    profile_parser = sub.add_parser("profile", help="Manage AWS profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_action", required=True)

    p = profile_sub.add_parser("add", help="Register an AWS profile")
    p.add_argument("alias", help="Short alias (e.g. 'prod')")
    p.add_argument("--aws-profile", default="default", help="AWS CLI profile name (default: default)")
    p.add_argument("--region", default="us-west-2", help="Default region (default: us-west-2)")
    p.add_argument("--name", help="Human-readable label")

    p = profile_sub.add_parser("remove", help="Remove a registered profile")
    p.add_argument("alias", help="Profile alias")

    profile_sub.add_parser("list", help="List registered profiles")

    # --- run (passthrough) ---
    run_parser = sub.add_parser("run", help="Run any AWS CLI command")
    run_parser.add_argument("alias", help="Profile alias")
    run_parser.add_argument("aws_args", nargs=argparse.REMAINDER, help="AWS CLI arguments (after --)")

    # --- ec2 ---
    ec2_parser = sub.add_parser("ec2", help="EC2 commands")
    ec2_parser.add_argument("alias", help="Profile alias")
    ec2_sub = ec2_parser.add_subparsers(dest="ec2_action", required=True)

    p = ec2_sub.add_parser("instances", help="List EC2 instances")
    p.add_argument("--state", choices=["running", "stopped", "all"], default="all", help="Filter by state")

    p = ec2_sub.add_parser("instance", help="Describe an instance")
    p.add_argument("id", help="Instance ID")

    p = ec2_sub.add_parser("start", help="Start an instance")
    p.add_argument("id", help="Instance ID")

    p = ec2_sub.add_parser("stop", help="Stop an instance")
    p.add_argument("id", help="Instance ID")

    p = ec2_sub.add_parser("reboot", help="Reboot an instance")
    p.add_argument("id", help="Instance ID")

    ec2_sub.add_parser("sg-list", help="List security groups")

    p = ec2_sub.add_parser("sg-rules", help="Show security group rules")
    p.add_argument("sg_id", help="Security Group ID")

    # --- s3 ---
    s3_parser = sub.add_parser("s3", help="S3 commands")
    s3_parser.add_argument("alias", help="Profile alias")
    s3_sub = s3_parser.add_subparsers(dest="s3_action", required=True)

    s3_sub.add_parser("buckets", help="List buckets")

    p = s3_sub.add_parser("ls", help="List objects in a bucket")
    p.add_argument("bucket", help="Bucket name")
    p.add_argument("--prefix", help="Key prefix filter")

    p = s3_sub.add_parser("cp", help="Copy files (local<->S3 or S3<->S3)")
    p.add_argument("src", help="Source path")
    p.add_argument("dst", help="Destination path")

    p = s3_sub.add_parser("sync", help="Sync directories")
    p.add_argument("src", help="Source path")
    p.add_argument("dst", help="Destination path")
    p.add_argument("--delete", action="store_true", help="Delete files in dst not in src")

    p = s3_sub.add_parser("rm", help="Remove objects")
    p.add_argument("path", help="S3 path to remove")
    p.add_argument("--recursive", action="store_true", help="Remove recursively")

    p = s3_sub.add_parser("presign", help="Generate presigned URL")
    p.add_argument("s3_url", help="S3 URL (s3://bucket/key)")
    p.add_argument("--expires", type=int, default=3600, help="URL expiry in seconds (default: 3600)")

    # --- rds ---
    rds_parser = sub.add_parser("rds", help="RDS commands")
    rds_parser.add_argument("alias", help="Profile alias")
    rds_sub = rds_parser.add_subparsers(dest="rds_action", required=True)

    rds_sub.add_parser("instances", help="List RDS instances")

    p = rds_sub.add_parser("instance", help="Describe an RDS instance")
    p.add_argument("id", help="DB instance identifier")

    p = rds_sub.add_parser("snapshots", help="List DB snapshots")
    p.add_argument("--db", help="Filter by DB instance identifier")

    p = rds_sub.add_parser("create-snapshot", help="Create a DB snapshot")
    p.add_argument("id", help="DB instance identifier")
    p.add_argument("--name", help="Snapshot identifier (default: auto-generated)")

    # --- cf (CloudFront) ---
    cf_parser = sub.add_parser("cf", help="CloudFront commands")
    cf_parser.add_argument("alias", help="Profile alias")
    cf_sub = cf_parser.add_subparsers(dest="cf_action", required=True)

    cf_sub.add_parser("distributions", help="List distributions")

    p = cf_sub.add_parser("distribution", help="Describe a distribution")
    p.add_argument("id", help="Distribution ID")

    p = cf_sub.add_parser("invalidate", help="Create cache invalidation")
    p.add_argument("id", help="Distribution ID")
    p.add_argument("--paths", required=True, help="Paths to invalidate (e.g. '/*')")

    # --- r53 (Route 53) ---
    r53_parser = sub.add_parser("r53", help="Route 53 commands")
    r53_parser.add_argument("alias", help="Profile alias")
    r53_sub = r53_parser.add_subparsers(dest="r53_action", required=True)

    r53_sub.add_parser("zones", help="List hosted zones")

    p = r53_sub.add_parser("records", help="List DNS records in a zone")
    p.add_argument("zone_id", help="Hosted zone ID")

    # --- lambda ---
    lambda_parser = sub.add_parser("lambda", help="Lambda commands")
    lambda_parser.add_argument("alias", help="Profile alias")
    lambda_sub = lambda_parser.add_subparsers(dest="lambda_action", required=True)

    lambda_sub.add_parser("functions", help="List functions")

    p = lambda_sub.add_parser("function", help="Describe a function")
    p.add_argument("name", help="Function name")

    p = lambda_sub.add_parser("invoke", help="Invoke a function")
    p.add_argument("name", help="Function name")
    p.add_argument("--payload", default="{}", help="JSON payload (default: {})")

    p = lambda_sub.add_parser("logs", help="Get recent logs")
    p.add_argument("name", help="Function name")
    p.add_argument("--limit", type=int, default=20, help="Number of log events (default: 20)")

    # --- ses ---
    ses_parser = sub.add_parser("ses", help="SES commands")
    ses_parser.add_argument("alias", help="Profile alias")
    ses_sub = ses_parser.add_subparsers(dest="ses_action", required=True)

    ses_sub.add_parser("identities", help="List email identities")

    p = ses_sub.add_parser("send", help="Send an email")
    p.add_argument("--from", dest="from_addr", required=True, help="Sender address")
    p.add_argument("--to", dest="to_addr", required=True, help="Recipient address")
    p.add_argument("--subject", required=True, help="Email subject")
    p.add_argument("--body", required=True, help="Email body text")

    ses_sub.add_parser("stats", help="Account sending stats")

    # --- acm ---
    acm_parser = sub.add_parser("acm", help="ACM commands (auto us-east-1)")
    acm_parser.add_argument("alias", help="Profile alias")
    acm_sub = acm_parser.add_subparsers(dest="acm_action", required=True)

    acm_sub.add_parser("certificates", help="List certificates")

    p = acm_sub.add_parser("certificate", help="Describe a certificate")
    p.add_argument("arn", help="Certificate ARN")

    # --- waf ---
    waf_parser = sub.add_parser("waf", help="WAF commands (auto us-east-1)")
    waf_parser.add_argument("alias", help="Profile alias")
    waf_sub = waf_parser.add_subparsers(dest="waf_action", required=True)

    waf_sub.add_parser("acls", help="List Web ACLs")

    p = waf_sub.add_parser("acl", help="Describe a Web ACL")
    p.add_argument("id", help="Web ACL ID or Name")

    p = waf_sub.add_parser("rules", help="List rules in a Web ACL")
    p.add_argument("acl_id", help="Web ACL ID or Name")

    # --- backup ---
    backup_parser = sub.add_parser("backup", help="AWS Backup commands")
    backup_parser.add_argument("alias", help="Profile alias")
    backup_sub = backup_parser.add_subparsers(dest="backup_action", required=True)

    backup_sub.add_parser("plans", help="List backup plans")

    p = backup_sub.add_parser("jobs", help="List backup jobs")
    p.add_argument("--state", choices=["COMPLETED", "FAILED", "RUNNING", "CREATED", "ABORTED"], help="Filter by state")

    p = backup_sub.add_parser("recovery-points", help="List recovery points in a vault")
    p.add_argument("vault_name", help="Backup vault name")

    # --- iam ---
    iam_parser = sub.add_parser("iam", help="IAM commands (global)")
    iam_parser.add_argument("alias", help="Profile alias")
    iam_sub = iam_parser.add_subparsers(dest="iam_action", required=True)

    iam_sub.add_parser("users", help="List IAM users")
    iam_sub.add_parser("roles", help="List IAM roles")

    p = iam_sub.add_parser("policies", help="List IAM policies")
    p.add_argument("--scope", choices=["Local", "AWS", "All"], help="Policy scope filter")

    p = iam_sub.add_parser("user", help="Describe an IAM user")
    p.add_argument("name", help="User name")

    # --- elasticache ---
    ec_parser = sub.add_parser("elasticache", help="ElastiCache commands")
    ec_parser.add_argument("alias", help="Profile alias")
    ec_sub = ec_parser.add_subparsers(dest="elasticache_action", required=True)

    ec_sub.add_parser("clusters", help="List cache clusters")

    p = ec_sub.add_parser("cluster", help="Describe a cache cluster")
    p.add_argument("id", help="Cache cluster ID")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    cmd = args.command

    if cmd == "profile":
        if args.profile_action == "add":
            cmd_profile_add(args)
        elif args.profile_action == "remove":
            cmd_profile_remove(args)
        elif args.profile_action == "list":
            cmd_profile_list(args)
    elif cmd == "run":
        cmd_run(args)
    elif cmd == "ec2":
        cmd_ec2(args)
    elif cmd == "s3":
        cmd_s3(args)
    elif cmd == "rds":
        cmd_rds(args)
    elif cmd == "cf":
        cmd_cf(args)
    elif cmd == "r53":
        cmd_r53(args)
    elif cmd == "lambda":
        cmd_lambda(args)
    elif cmd == "ses":
        cmd_ses(args)
    elif cmd == "acm":
        cmd_acm(args)
    elif cmd == "waf":
        cmd_waf(args)
    elif cmd == "backup":
        cmd_backup(args)
    elif cmd == "iam":
        cmd_iam(args)
    elif cmd == "elasticache":
        cmd_elasticache(args)


if __name__ == "__main__":
    main()
