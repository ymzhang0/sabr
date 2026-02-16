from aiida import orm

def get_node_file_content(pk, filename, source="folder"):
    """
    Retrieve text content of a file from a node's repository or file output.
    source: 'folder' (Process/FolderData) or 'repository' (The node's own repo)
    """
    try:
        node = orm.load_node(pk)
        content = ""
        
        if source == "repository" or source == "Virtual.Repository":
             content = node.base.repository.get_object_content(filename)
        else:
             # For FolderData or similar, get_object_content works on the node itself
             content = node.get_object_content(filename)
             
        # Attempt decode
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"
