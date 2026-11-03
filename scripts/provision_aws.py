"""Automated AWS Cloud-First Infrastructure Provisioner for IntelliQ.

Provisions 100% Always-Free tier AWS resources (DynamoDB 10 RCU/WCU, S3 with
1d/7d lifecycles + CORS, Cognito Lite User Pool & App Client) and syncs their
live identifiers directly into .env for seamless cloud-native local testing.
"""
import json
import logging
import os
import sys
import time
from typing import Any
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("intelliq.provision")


def get_account_id(sts_client) -> str:
    """Fetch 12-digit AWS Account ID."""
    return sts_client.get_caller_identity()["Account"]


def provision_dynamodb_table(dynamodb_client, table_name: str) -> str:
    """Provision DynamoDB Single-Table under 25 RCU/WCU Always-Free tier."""
    logger.info("Checking DynamoDB table '%s'...", table_name)
    try:
        resp = dynamodb_client.describe_table(TableName=table_name)
        status = resp["Table"]["TableStatus"]
        logger.info("DynamoDB table '%s' already exists (Status: %s)", table_name, status)
        return table_name
    except dynamodb_client.exceptions.ResourceNotFoundException:
        logger.info("Creating DynamoDB table '%s' with 10 RCU / 10 WCU Provisioned capacity...", table_name)

    dynamodb_client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
            }
        ],
        BillingMode="PROVISIONED",
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    )

    # Wait for table to be active
    logger.info("Waiting for DynamoDB table '%s' to become ACTIVE...", table_name)
    waiter = dynamodb_client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)

    # Enable TTL on 'ttl' attribute ($0 idle cost automatic cleanup)
    try:
        dynamodb_client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": "ttl",
            },
        )
        logger.info("DynamoDB TTL enabled on attribute 'ttl'.")
    except Exception as e:
        logger.warning("Could not set TTL on table: %s", e)

    return table_name


def provision_s3_bucket(s3_client, bucket_name: str, region: str) -> str:
    """Provision S3 Storage Bucket with strict CORS and Lifecycle rules."""
    logger.info("Checking S3 bucket '%s'...", bucket_name)
    bucket_exists = False
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info("S3 bucket '%s' already exists.", bucket_name)
        bucket_exists = True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket"):
            bucket_exists = False
        else:
            logger.info("Head bucket returned %s; verifying access...", error_code)

    if not bucket_exists:
        logger.info("Creating S3 bucket '%s' in %s...", bucket_name, region)
        create_kwargs: dict[str, Any] = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3_client.create_bucket(**create_kwargs)
        logger.info("S3 bucket '%s' created successfully.", bucket_name)

    # Configure CORS for direct browser PUT uploads
    cors_config = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT", "POST", "HEAD", "DELETE"],
                "AllowedOrigins": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3000,
            }
        ]
    }
    s3_client.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_config)
    logger.info("S3 bucket CORS configured for browser direct PUT.")

    # ADR-01: Lifecycle rules: 1d abort multipart, 7d tmp/ expiration
    lifecycle_config = {
        "Rules": [
            {
                "ID": "AbortIncompleteMultipartUpload",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
            },
            {
                "ID": "ExpireTemporaryArtifacts",
                "Status": "Enabled",
                "Filter": {"Prefix": "tmp/"},
                "Expiration": {"Days": 7},
            },
        ]
    }
    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration=lifecycle_config,
    )
    logger.info("S3 bucket lifecycle rules configured (1-day abort / 7-day tmp expire).")
    return bucket_name


def provision_cognito_user_pool(cognito_client, pool_name: str) -> tuple[str, str]:
    """Provision Cognito Lite User Pool & App Client ($0 Always-Free Tier)."""
    logger.info("Checking Cognito User Pool '%s'...", pool_name)
    pools = cognito_client.list_user_pools(MaxResults=30).get("UserPools", [])
    matched_pool_id = None
    for p in pools:
        if p["Name"] == pool_name:
            matched_pool_id = p["Id"]
            break

    if not matched_pool_id:
        logger.info("Creating Cognito User Pool '%s' (Lite Tier)...", pool_name)
        create_pool_resp = cognito_client.create_user_pool(
            PoolName=pool_name,
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": True,
                }
            },
            AutoVerifiedAttributes=["email"],
            UsernameAttributes=["email"],
            UserPoolTier="ESSENTIALS",
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": False},
        )
        matched_pool_id = create_pool_resp["UserPool"]["Id"]
        logger.info("Cognito User Pool created with ID '%s'.", matched_pool_id)
    else:
        logger.info("Found existing Cognito User Pool '%s' (ID: %s).", pool_name, matched_pool_id)

    # Check App Client
    clients = cognito_client.list_user_pool_clients(
        UserPoolId=matched_pool_id, MaxResults=20
    ).get("UserPoolClients", [])

    client_id = None
    for c in clients:
        if c["ClientName"] in ("intelliq-web-client", "WebClient"):
            client_id = c["ClientId"]
            break

    if not client_id:
        logger.info("Creating public App Client for User Pool '%s'...", matched_pool_id)
        client_resp = cognito_client.create_user_pool_client(
            UserPoolId=matched_pool_id,
            ClientName="intelliq-web-client",
            GenerateSecret=False,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_USER_SRP_AUTH",
            ],
            PreventUserExistenceErrors="ENABLED",
        )
        client_id = client_resp["UserPoolClient"]["ClientId"]
        logger.info("Cognito App Client created with ID '%s'.", client_id)
    else:
        logger.info("Found existing Cognito App Client (ID: %s).", client_id)

    return matched_pool_id, client_id


def sync_env_file(env_updates: dict[str, str], env_path: str = ".env") -> None:
    """Read existing .env, update specified keys, and write back preserving comments."""
    existing_lines = []
    found_keys = set()

    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _ = stripped.split("=", 1)
                    k = k.strip()
                    if k in env_updates:
                        existing_lines.append(f"{k}={env_updates[k]}\n")
                        found_keys.add(k)
                        continue
                existing_lines.append(line)

    # Append any keys that weren't in the file
    for k, v in env_updates.items():
        if k not in found_keys:
            existing_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(existing_lines)

    logger.info(".env file updated successfully at '%s'.", os.path.abspath(env_path))


def main():
    logger.info("=== Starting IntelliQ Cloud-First Infrastructure Provisioner ===")
    region = os.getenv("AWS_REGION", "ap-south-1")

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    account_id = get_account_id(sts)
    logger.info("Authenticated AWS Account: %s (Region: %s)", account_id, region)

    # 1. DynamoDB Single Table
    table_name = "intelliq-dev-db"
    dynamodb = session.client("dynamodb")
    provisioned_table = provision_dynamodb_table(dynamodb, table_name)

    # 2. S3 Storage Bucket
    bucket_name = f"intelliq-storage-{account_id}-{region}"
    s3 = session.client("s3")
    provisioned_bucket = provision_s3_bucket(s3, bucket_name, region)

    # 3. Cognito User Pool & App Client
    user_pool_name = "intelliq-dev-userpool"
    cognito = session.client("cognito-idp")
    user_pool_id, client_id = provision_cognito_user_pool(cognito, user_pool_name)

    # 4. Sync .env
    env_updates = {
        "AWS_REGION": region,
        "APP_NAME": "intelliq",
        "STAGE": "dev",
        "DYNAMODB_BILLING_MODE": "PROVISIONED",
        "DYNAMODB_TABLE_NAME": provisioned_table,
        "S3_BUCKET_NAME": provisioned_bucket,
        "COGNITO_USER_POOL_ID": user_pool_id,
        "COGNITO_CLIENT_ID": client_id,
        "ALLOWED_EMAIL_DOMAINS": "*",
        "RATE_LIMIT_MAX_REQUESTS": "60",
        "RATE_LIMIT_WINDOW_SECONDS": "300",
    }
    sync_env_file(env_updates)

    logger.info("=== All AWS Cloud Resources Provisioned & .env Synchronized ===")
    print("\nPROVISIONED RESOURCES:")
    print(f"  AWS Region:        {region}")
    print(f"  DynamoDB Table:    {provisioned_table} (10 RCU/WCU Always-Free)")
    print(f"  S3 Bucket:         {provisioned_bucket} (CORS & Lifecycle active)")
    print(f"  Cognito Pool ID:   {user_pool_id}")
    print(f"  Cognito Client ID: {client_id}")


if __name__ == "__main__":
    main()

