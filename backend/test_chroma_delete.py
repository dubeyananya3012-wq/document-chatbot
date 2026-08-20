import traceback
import sys
import os

# add backend paths
backend_path = r"c:\Users\Administrator\Downloads\document-chatbot\backend"
sys.path.append(backend_path)
os.environ["ENV"] = "development"

# Set current directory to backend so config can find .env
os.chdir(backend_path)

from app.services.vectorstore import delete_user_document, _get_collection

try:
    print("Getting collection...")
    col = _get_collection()
    print("Collection retrieved:", col)
    
    print("Attempting to delete non-existent user document...")
    delete_user_document("test_user_id_123", "non_existent_file.pdf")
    print("Deletion completed without errors.")
except Exception as e:
    print("Error occurred during delete:")
    traceback.print_exc()
