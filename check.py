import os
import base64
import requests
import streamlit as st

st.cache_data.clear()

# GitHub configurations
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = "2005lakshmi/mitmpp1"  # Update with your repo
GITHUB_PATH = "SEM"  # Root folder
PASSWORD = st.secrets["general"]["password"]

def create_folder(path):
    """Create folder with null.txt at given path"""
    file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}/null.txt"
    encoded = base64.b64encode(b"null").decode()
    data = {"message": f"Create {path}", "content": encoded}
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.put(file_url, json=data, headers=headers)
    return response.status_code == 201

def get_folders(path):
    """Get list of folders in given path"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [item['name'] for item in response.json() if item['type'] == "dir"]
    return []

def get_files(path):
    """Get list of files in given path"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [item['name'] for item in response.json() if item['type'] == "file"]
    return []

def delete_item(path):
    """Delete file or folder recursively with proper SHA handling"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Check if path is file or folder
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return False
    
    items = response.json()
    if not isinstance(items, list):  # Single file
        sha = items['sha']
        response = requests.delete(url, headers=headers, json={
            "message": f"Delete {path}",
            "sha": sha
        })
        return response.status_code == 200
    
    # Delete folder contents recursively
    for item in items:
        if item['type'] == 'dir':
            delete_item(item['path'])
        else:
            delete_item(item['path'])
    
    return True

def rename_file(old_path, new_name):
    """Rename file by creating copy and deleting original"""
    # Get file content
    content = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{old_path}").content
    encoded = base64.b64encode(content).decode()
    
    # Create new path
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    
    # Create new file
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{new_path}"
    response = requests.put(url,
                          headers={"Authorization": f"token {GITHUB_TOKEN}"},
                          json={
                              "message": f"Rename {os.path.basename(old_path)} to {new_name}",
                              "content": encoded
                          })
    
    if response.status_code == 201:
        # Delete old file
        return delete_item(old_path)
    return False

# Admin Page Functions
def admin_page():
    st.title("Admin Portal")

    with st.expander("Create New Semester"):
        new_sem = st.text_input("Enter Semester Name")
        if st.button("Create Semester"):
            if create_folder(f"{GITHUB_PATH}/{new_sem}"):
                st.success(f"Semester {new_sem} created!")
            else:
                st.error("Creation failed!")

    with st.expander("Create Subject"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters)
        new_subject = st.text_input("Enter Subject Name")
        if st.button("Create Subject"):
            if create_folder(f"{GITHUB_PATH}/{selected_sem}/{new_subject}"):
                st.success("Subject created!")
            else:
                st.error("Creation failed!")

    with st.expander("Upload Files"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Choose Semester", semesters, key="upload_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        selected_subject = st.selectbox("Choose Subject", subjects, key="upload_sub")
        
        uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True)
        if uploaded_files:
            for file in uploaded_files:
                content = file.getvalue()
                encoded = base64.b64encode(content).decode()
                url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}/{selected_sem}/{selected_subject}/{file.name}"
                response = requests.put(url,
                                      headers={"Authorization": f"token {GITHUB_TOKEN}"},
                                      json={"message": f"Add {file.name}", "content": encoded})
                if response.status_code == 201:
                    st.success(f"Uploaded {file.name}!")
                else:
                    st.error(f"Failed to upload {file.name}: {response.json().get('message', '')}")

    with st.expander("Manage Files"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters, key="manage_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        selected_subject = st.selectbox("Select Subject", subjects, key="manage_sub")
        
        files = get_files(f"{GITHUB_PATH}/{selected_sem}/{selected_subject}")
        for file in files:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(file)
            with col2:
                new_name = st.text_input(f"New name for {file}", key=f"rename_{file}")
            with col3:
                if st.button(f"Rename", key=f"rename_btn_{file}"):
                    if new_name and new_name != file:
                        old_path = f"{GITHUB_PATH}/{selected_sem}/{selected_subject}/{file}"
                        if rename_file(old_path, new_name):
                            st.success("Renamed!")
                            st.rerun()
                        else:
                            st.error("Rename failed")
                if st.button(f"Delete", key=f"del_{file}"):
                    if delete_item(f"{GITHUB_PATH}/{selected_sem}/{selected_subject}/{file}"):
                        st.success("Deleted!")
                        st.rerun()
                    else:
                        st.error("Delete failed")

    with st.expander("Delete Folders"):
        semesters = get_folders(GITHUB_PATH)
        selected_sem = st.selectbox("Select Semester", semesters, key="del_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        selected_subject = st.selectbox("Select Subject", subjects, key="del_sub")
        
        if st.button("Delete Subject Folder"):
            if delete_item(f"{GITHUB_PATH}/{selected_sem}/{selected_subject}"):
                st.success("Deleted subject folder!")
                st.rerun()
            else:
                st.error("Delete failed")
        
        if st.button("Delete Semester Folder"):
            if delete_item(f"{GITHUB_PATH}/{selected_sem}"):
                st.success("Deleted semester folder!")
                st.rerun()
            else:
                st.error("Delete failed")

# Default User Page
def default_page():
    st.title("Study Materials Repository")
    
    # Password check
    search_query = st.text_input("Search folders...", key="search")
    if search_query == PASSWORD:
        st.session_state.admin = True
        st.rerun()
    
    # Folder navigation
    semesters = get_folders(GITHUB_PATH)
    if semesters:
        selected_sem = st.selectbox("Select Semester", semesters, key="user_sem")
        subjects = get_folders(f"{GITHUB_PATH}/{selected_sem}")
        if subjects:
            selected_subject = st.selectbox("Select Subject", subjects, key="user_sub")
            files = get_files(f"{GITHUB_PATH}/{selected_sem}/{selected_subject}")
            
            if files:
                st.subheader("Available Files:")
                for file in files:
                    download_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PATH}/{selected_sem}/{selected_subject}/{file}"
                    st.download_button(
                        label=file,
                        data=requests.get(download_url).content,
                        file_name=file
                    )
            else:
                st.info("No files available in this subject")
        else:
            st.info("No subjects available in this semester")
    else:
        st.info("No semesters available")

# Main App
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
