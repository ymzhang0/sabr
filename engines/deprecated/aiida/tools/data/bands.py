# engines/aiida/tools/bands.py
from aiida import orm

def get_bands_plot_data(pk: int): # 🚩 显式指定为 str (与之前 inspect_process 的修复一致)
    """
    Retrieve plotting data from a BandsData node for plotting.
    
    Args:
        pk (str): The primary key (PK) or UUID of the BandsData node.
    """
    try:
        # load_node 在 AiiDA 中可以处理字符串格式的 PK
        node = orm.load_node(pk)
        
        if hasattr(node, '_matplotlib_get_dict'):
            return node._matplotlib_get_dict()
            
    except Exception as e:
        return f"Error getting bands data for {pk}: {e}"
    
    return "Error: Node is not a compatible BandsData type."