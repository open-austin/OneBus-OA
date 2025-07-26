import os
from google.cloud import storage
from dotenv import load_dotenv
import pandas as pd
from io import StringIO
import base64
import json
from google.oauth2 import service_account

# Load environment variables once when module is imported
load_dotenv()

# def setup_google_credentials():
#     """Handle credentials from either file path or base64 environment variable"""
#     creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
#     # If using base64-encoded credentials in production
#     if 'GOOGLE_CREDS_BASE64' in os.environ:
#         secrets_dir = Path('./secrets')
#         secrets_dir.mkdir(exist_ok=True)
        
#         creds_path = secrets_dir / 'service-account.json'
#         decoded_creds = base64.b64decode(os.environ['GOOGLE_CREDS_BASE64'])
#         creds_path.write_bytes(decoded_creds)
#         os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(creds_path)
    
#     # Verify credentials exist
#     if not creds_path or not Path(creds_path).exists():
#         raise FileNotFoundError(
#             f"Google credentials not found at {creds_path}. "
#             "Set either GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CREDS_BASE64"
#         )

def read_gcs_csv(filename="filtered_pois.csv"):
    """Directly read a CSV file from GCS and return as DataFrame"""
    try:
        # Get base64 credentials from environment and decode
        creds_b64 = os.getenv("GOOGLE_CREDS_BASE64")
        if not creds_b64:
            raise ValueError("GOOGLE_CREDS_BASE64 environment variable not set")
            
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_dict = json.loads(creds_json)
        
        print("Initializing Client")
        # Initialize client with the decoded credentials
        storage_client = storage.Client.from_service_account_info(creds_dict)
        
        # Get bucket and path from environment
        bucket_name = os.getenv('GCS_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME environment variable not set")
            
        folder_prefix = os.getenv('GCS_FOLDER_PREFIX', '')
        
        # Clean path construction
        full_path = filename if not folder_prefix else f"{folder_prefix}/{filename}"
        full_path = full_path.replace('//', '/')
        
        print(f'Attempting to read: gs://{bucket_name}/{full_path}')
        
        # Get blob
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(full_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"File gs://{bucket_name}/{full_path} not found")
        
        # Read content
        content = blob.download_as_text()
        return pd.read_csv(StringIO(content))
        
    except Exception as e:
        print(f"Error reading {filename}: {str(e)}")
        raise