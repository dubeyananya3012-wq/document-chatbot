import sys
import os
import traceback

backend_path = r"c:\Users\Administrator\Downloads\document-chatbot\backend"
sys.path.append(backend_path)
os.environ["ENV"] = "development"
os.chdir(backend_path)

import chromadb
from chromadb.config import Settings
from app.config import get_settings

settings = get_settings()

try:
    print("API Key:", settings.CHROMA_API_KEY[:10] + "...")
    print("Tenant:", settings.CHROMA_TENANT)
    
    # Configure correct client settings
    c_settings = Settings(
        chroma_api_impl="chromadb.api.fastapi.FastAPI",
        chroma_server_host="api.trychroma.com",
        chroma_server_http_port=443,
        chroma_server_ssl_enabled=True,
        chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
        chroma_client_auth_credentials=settings.CHROMA_API_KEY,
        chroma_auth_token_transport_header="X-Chroma-Token",
        chroma_overwrite_singleton_tenant_database_access_from_auth=True
    )
    
    print("Attempting to connect with AdminClient...")
    admin_client = chromadb.AdminClient(settings=c_settings)
    print("Admin client initialized.")
    
    # List databases
    try:
        databases = admin_client.list_databases(tenant=settings.CHROMA_TENANT)
        print("Existing databases of tenant:", databases)
    except Exception as e:
        print("Failed to list databases:")
        traceback.print_exc()
        databases = []
        
    if "default" not in databases and settings.CHROMA_DATABASE not in databases:
        print(f"Database '{settings.CHROMA_DATABASE}' not found. Trying to create it...")
        try:
            admin_client.create_database(name=settings.CHROMA_DATABASE, tenant=settings.CHROMA_TENANT)
            print(f"Successfully created '{settings.CHROMA_DATABASE}' database!")
            
            # double check
            dbs = admin_client.list_databases(tenant=settings.CHROMA_TENANT)
            print("Databases now:", dbs)
        except Exception as e2:
            print(f"Failed to create '{settings.CHROMA_DATABASE}' database.")
            traceback.print_exc()
    else:
        print(f"Database '{settings.CHROMA_DATABASE}' already exists.")
            
except Exception as e:
    traceback.print_exc()
