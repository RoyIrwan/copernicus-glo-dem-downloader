"""Anonymous S3 client for the public Copernicus DEM AWS Open Data buckets."""

from __future__ import annotations

import boto3
from botocore import UNSIGNED
from botocore.client import Config as BotoConfig

# AWS Open Data buckets are public; any valid region works for signature-less
# requests since boto3 follows the bucket's actual location transparently.
DEFAULT_REGION = "us-west-2"


def create_client(region: str = DEFAULT_REGION):
    return boto3.client(
        "s3",
        region_name=region,
        config=BotoConfig(signature_version=UNSIGNED),
    )
