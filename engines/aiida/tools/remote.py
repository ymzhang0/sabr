from aiida import orm
import tempfile
import os

def list_remote_files(pk):
    """
    List files in a RemoteData node's remote directory.
    Returns a list of filenames or an error message string.
    """
    try:
        node = orm.load_node(pk)
        return node.listdir()
    except Exception as e:
        return f"Error listing files: {e}"

def get_remote_file_content(pk, filename):
    """
    Retrieve content of a file from a RemoteData node.
    Downloads to a temp file and reads it.
    """
    try:
        node = orm.load_node(pk)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_file = os.path.join(tmpdir, filename)
            node.getfile(filename, dest_file)
            
            with open(dest_file, 'r', errors='replace') as fobj:
                content = fobj.read()
            return content
            
    except Exception as e:
        return f"Error retrieving file: {e}"
