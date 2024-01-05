import boto3
import botocore
from django.conf import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=botocore.client.Config(signature_version="s3v4"),
    )


def s3_object_url(method, key, bucket):
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod=f"{method.lower()}_object", Params={"Bucket": bucket, "Key": key}
    )


def s3_object_size(key, bucket):
    s3 = get_s3_client()
    return s3.head_object(Bucket=bucket, Key=key).get("ContentLength", 0)


def s3_delete_key(key, bucket):
    s3 = get_s3_client()
    s3.delete_object(
        Bucket=bucket,
        Key=key,
    )
