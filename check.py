import os
import base64
import json
import requests
import streamlit as st

st.cache_data.clear()

# ======================
# Configuration
# ======================
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = "2005lakshmi/mitmpp1"
GITHUB_PATH = "SEM"
PASSWORD = st.secrets["general"]["password"]
DESCRIPTION_FILE = "_descriptions.json"

# ======================
# Helper Functions
# ======================
def handle_github_error(response, operation):
    """Display detailed error message for GitHub operations"""
    try:
        error_msg = response.json().get('message', 'Unknown error')
        st.error(f"{operation} failed: {error_msg}")
    except:
        st.error(f"{operation} failed with status {response.status_code}")

def create_folder(path):
    """Create folder with null.txt"""
    try:
        file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}/null.txt"
        encoded = base64.b64encode(b"null").decode()
        response = requests.put(
            file_url,
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={"message": f"Create {path}", "content": encoded}
        )
        if response.status_code == 201:
            return True
        handle_github_error(response, "Folder creation")
        return False
    except Exception as e:
        st.error(f"Network error: {str(e)}")
        return False

def get_folders(path):
    """Get list of folders with error handling"""
    try:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"}
        )
        if response.status_code == 200:
            return [item['name'] for item in response.json() if item['type'] == "dir"]
        handle_github_error(response, "Fetch folders")
        return []
    except Exception as e:
        st.error(f"Network error: {str(e)}")
        return []

def get_files(path):
    """Get list of files with error handling"""
    try:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"}
        )
        if response.status_code == 200:
            return [item['name'] for item in response.json() if item['type'] == "file"]
        handle_github_error(response, "Fetch files")
        return []
    except Exception as e:
        st.error(f"Network error: {str(e)}")
        return []

def get_descriptions(semester, subject):
    """Get descriptions with error handling"""
    try:
        path = f"{GITHUB_PATH}/{semester}/{subject}/{DESCRIPTION_FILE}"
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"}
        )
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode()
            return json.loads(content)
        return {}
    except Exception as e:
        st.error(f"Failed to load descriptions: {str(e)}")
        return {}

def save_descriptions(semester, subject, descriptions):
    """Save descriptions with error handling"""
    try:
        path = f"{GITHUB_PATH}/{semester}/{subject}/{DESCRIPTION_FILE}"
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        
        # Get existing SHA if available
        sha = None
        response = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
        if response.status_code == 200:
            sha = response.json().get('sha')
        
        content = json.dumps(descriptions, indent=2)
        data = {
            "message": "Update descriptions",
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha
        }
        
        response = requests.put(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}, json=data)
        if response.status_code in [200, 201]:
            return True
        handle_github_error(response, "Save descriptions")
        return False
    except Exception as e:
        st.error(f"Network error: {str(e)}")
        return False

def rename_file(old_path, new_name):
    """Safe file rename with description updates"""
    try:
        # Validate path structure
        dir_path = os.path.dirname(old_path)
        parts = dir_path.split('/')
        if len(parts) != 3 or parts[0] != GITHUB_PATH:
            st.error("Invalid path structure for renaming")
            return False

        semester, subject = parts[1], parts[2]
        original_name = os.path.basename(old_path)
        descriptions = get_descriptions(semester, subject)
        desc = descriptions.get(original_name, "")

        # Get file content
        response = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{old_path}")
        if response.status_code != 200:
            handle_github_error(response, "File fetch")
            return False
        content = response.content

        # Create new file
        new_path = f"{dir_path}/{new_name}"
        response = requests.put(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{new_path}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={
                "message": f"Rename {original_name} to {new_name}",
                "content": base64.b64encode(content).decode()
            }
        )
        
        if response.status_code != 201:
            handle_github_error(response, "File rename")
            return False

        # Update descriptions
        if original_name in descriptions:
            descriptions[new_name] = descriptions.pop(original_name)
            if not save_descriptions(semester, subject, descriptions):
                st.error("Failed to update descriptions during rename")
                return False

        # Delete old file
        if not delete_item(old_path):
            st.error("Failed to delete original file after rename")
            return False

        return True
    except Exception as e:
        st.error(f"Rename error: {str(e)}")
        return False

def delete_item(path):
    """Safe deletion with description cleanup"""
    try:
        # Handle description cleanup
        parts = path.split('/')
        if len(parts) == 4 and parts[0] == GITHUB_PATH:  # File deletion
            semester, subject, filename = parts[1], parts[2], parts[3]
            descriptions = get_descriptions(semester, subject)
            if filename in descriptions:
                del descriptions[filename]
                if not save_descriptions(semester, subject, descriptions):
                    st.error("Failed to update descriptions during deletion")

        # GitHub deletion API
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        response = requests.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
        if response.status_code != 200:
            handle_github_error(response, "Deletion prep")
            return False

        items = response.json()
        if not isinstance(items, list):  # Single file
            sha = items['sha']
            response = requests.delete(
                url,
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"message": f"Delete {path}", "sha": sha}
            )
            if response.status_code != 200:
                handle_github_error(response, "File deletion")
                return False
            return True

        # Folder deletion
        for item in items:
            if not delete_item(item['path']):
                return False
        return True
    except Exception as e:
        st.error(f"Deletion error: {str(e)}")
        return False

# ======================
# Admin Interface
# ======================
def admin_page():
    st.title("Admin Portal")

    # Semester Creation
    with st.expander("Create New Semester"):
        new_sem = st.text_input("Semester Name (e.g., 'Sem1')")
        if st.button("Create Semester"):
            if new_sem:
                if create_folder(f"{GITHUB_PATH}/{new_sem}"):
                    st.success(f"Created semester: {new_sem}")
                else:
                    st.error("Semester creation failed")
            else:
                st.warning("Please enter a semester name")

    # Subject Creation
    with st.expander("Create Subject"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters, key="create_sub_sem")
        new_sub = st.text_input("Subject Name")
        if st.button("Create Subject"):
            if new_sub:
                path = f"{GITHUB_PATH}/{selected_sem}/{new_sub}"
                if create_folder(path):
                    # Initialize empty descriptions
                    save_descriptions(selected_sem, new_sub, {})
                    st.success(f"Created subject: {new_sub}")
                else:
                    st.error("Subject creation failed")
            else:
                st.warning("Please enter a subject name")

    # File Upload
    with st.expander("Upload Files"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters, key="upload_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        selected_sub = st.selectbox("Select Subject", subjects, key="upload_sub")
        
        uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)
        if uploaded_files:
            for file in uploaded_files:
                content = file.getvalue()
                try:
                    response = requests.put(
                        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}/{selected_sem}/{selected_sub}/{file.name}",
                        headers={"Authorization": f"token {GITHUB_TOKEN}"},
                        json={
                            "message": f"Add {file.name}",
                            "content": base64.b64encode(content).decode()
                        }
                    )
                    if response.status_code == 201:
                        st.success(f"Uploaded {file.name}")
                    else:
                        handle_github_error(response, "File upload")
                except Exception as e:
                    st.error(f"Upload failed: {str(e)}")

    # File Management
    with st.expander("Manage Files"):
        semesters = get_folders(GITHUB_PATH)
        if not semesters:
            st.info("No semesters available")
            return
            
        selected_sem = st.selectbox("Select Semester", semesters, key="manage_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        if not subjects:
            st.info("No subjects in this semester")
            return
            
        selected_sub = st.selectbox("Select Subject", subjects, key="manage_sub")
        files = get_files(f"{GITHUB_PATH}/{selected_sem}/{selected_sub}")
        descriptions = get_descriptions(selected_sem, selected_sub)
        
        if not files:
            st.info("No files in this subject")
            return
            
        for file in files:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    current_desc = descriptions.get(file, "")
                    new_desc = st.text_area(
                        f"Description for {file}",
                        value=current_desc,
                        key=f"desc_{file}",
                        height=100
                    )
                    
                with col2:
                    new_name = st.text_input("New name", key=f"rename_{file}")
                    if st.button("🔄 Update", key=f"update_{file}"):
                        if new_desc != current_desc:
                            if update_file_description(selected_sem, selected_sub, file, new_desc):
                                st.success("Description updated!")
                            else:
                                st.error("Update failed")
                        else:
                            st.info("No changes to save")
                    
                    if st.button("❌ Delete", key=f"del_{file}"):
                        if delete_item(f"{GITHUB_PATH}/{selected_sem}/{selected_sub}/{file}"):
                            st.success("File deleted")
                            st.rerun()
                        else:
                            st.error("Deletion failed")
                    
                    if new_name and st.button("✏️ Rename", key=f"rename_btn_{file}"):
                        old_path = f"{GITHUB_PATH}/{selected_sem}/{selected_sub}/{file}"
                        if rename_file(old_path, new_name):
                            st.success("File renamed")
                            st.rerun()
                        else:
                            st.error("Rename failed")

    # Folder Deletion
    with st.expander("Delete Folders", True):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters, key="del_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete Semester", type="primary"):
                if delete_item(f"{GITHUB_PATH}/{selected_sem}"):
                    st.success("Semester deleted")
                    st.rerun()
                else:
                    st.error("Deletion failed")
        
        with col2:
            selected_sub = st.selectbox("Select Subject", subjects, key="del_sub")
            if st.button("Delete Subject", type="primary"):
                if delete_item(f"{GITHUB_PATH}/{selected_sem}/{selected_sub}"):
                    st.success("Subject deleted")
                    st.rerun()
                else:
                    st.error("Deletion failed")

# ======================
# User Interface
# ======================
def default_page():
    st.title("Study Materials Repository")
    
    # Password Check
    search = st.text_input("Search folders...", key="search")
    if search == PASSWORD:
        st.session_state.admin = True
        st.rerun()
    elif search:
        st.info("No matching folders found")

    # Navigation
    semesters = get_folders(GITHUB_PATH)
    if not semesters:
        st.info("No semesters available")
        return
        
    selected_sem = st.radio("Select Semester", semesters, key="user_sem")
    subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
    
    if not subjects:
        st.info("No subjects in this semester")
        return
        
    selected_sub = st.radio("Select Subject", subjects, key="user_sub")
    files = get_files(f"{GITHUB_PATH}/{selected_sem}/{selected_sub}")
    descriptions = get_descriptions(selected_sem, selected_sub)
    
    if not files:
        st.info("No files in this subject")
        return
        
    st.subheader("Available Files")
    for file in files:
        with st.expander(file):
            st.caption(descriptions.get(file, "No description available"))
            download_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PATH}/{selected_sem}/{selected_sub}/{file}"
            st.download_button(
                label="Download File",
                data=requests.get(download_url).content,
                file_name=file
            )

# ======================
# Main App
# ======================
def main():
    if 'admin' not in st.session_state:
        st.session_state.admin = False
    
    if st.session_state.admin:
        admin_page()
        if st.button("Exit Admin Mode"):
            st.session_state.admin = False
            st.rerun()
    else:
        default_page()

if __name__ == "__main__":
    main()
