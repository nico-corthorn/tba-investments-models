import logging
import os
import subprocess
import sys

import boto3

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_script(s3_uri, local_path):
    """Download a script from S3 and make it executable."""
    logger.info("Attempting to download from %s to %s", s3_uri, local_path)
    if not s3_uri.startswith("s3://"):
        return local_path

    bucket = s3_uri.split("/")[2]
    key = "/".join(s3_uri.split("/")[3:])

    logger.info("Downloading from bucket: %s, key: %s", bucket, key)
    s3 = boto3.client("s3")
    s3.download_file(bucket, key, local_path)
    os.chmod(local_path, 0o755)
    logger.info("Downloaded and made executable: %s", local_path)
    return local_path


def install_tbainvestetl():
    """Install the tbainvestetl package from AWS CodeArtifact."""
    logger.info("Installing tbainvestetl package from AWS CodeArtifact...")
    try:
        aws_account_id = os.environ["AWS_ACCOUNT_ID"]
        aws_region = os.environ["AWS_REGION"]
        domain = "tba-investments"
        repository = "tba-investments-etl"

        logger.info("Using AWS account ID: %s", aws_account_id)
        logger.info("Using AWS region: %s", aws_region)

        # Get authorization token using boto3
        codeartifact = boto3.client("codeartifact")
        response = codeartifact.get_authorization_token(
            domain=domain,
            domainOwner=aws_account_id,
        )
        auth_token = response["authorizationToken"]

        # Build the repository URL with the token
        domain_url = f"{domain}-{aws_account_id}.d.codeartifact.{aws_region}.amazonaws.com"
        repo_url = f"https://{domain_url}/pypi/{repository}/simple/"

        # Install the package using pip
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--index-url",
                repo_url,
                "--extra-index-url",
                "https://pypi.org/simple",
                "tbainvestetl",
            ],
            check=True,
            env={**os.environ, "AWS_CODEARTIFACT_AUTH_TOKEN": auth_token},
        )

        logger.info("Successfully installed tbainvestetl.")
    except Exception as e:
        logger.error("Failed to install tbainvestetl: %s", str(e))
        raise


def main():
    """Main entry point for the script runner."""
    logger.info("Script runner started")
    logger.info("Python executable: %s", sys.executable)
    logger.info("PYTHONPATH: %s", os.environ.get("PYTHONPATH", "not set"))
    logger.info("Current working directory: %s", os.getcwd())
    logger.info("Directory contents: %s", os.listdir("."))

    # Install tbainvestetl package
    install_tbainvestetl()

    # Check if we're in processing or transform mode
    if os.environ.get("SAGEMAKER_PROGRAM") == "serve":
        logger.info("Running in serve mode")
        serve_script = download_script(
            os.environ.get("SERVE_SCRIPT_URI", "/opt/ml/code/serve"), "/opt/ml/code/serve"
        )
        _ = download_script(
            os.environ.get("INFERENCE_SCRIPT_URI", "/opt/ml/code/inference.py"),
            "/opt/ml/code/inference.py",
        )
        subprocess.run([sys.executable, serve_script], check=True, env=os.environ)
    else:
        logger.info("Running in processing mode")
        preprocess_script = download_script(
            os.environ.get("PREPROCESSING_SCRIPT_URI", "/opt/ml/code/preprocessing.py"),
            "/opt/ml/code/preprocessing.py",
        )
        logger.info("Running preprocessing script: %s", preprocess_script)
        subprocess.run(
            [sys.executable, preprocess_script] + sys.argv[1:], check=True, env=os.environ
        )


if __name__ == "__main__":
    main()
