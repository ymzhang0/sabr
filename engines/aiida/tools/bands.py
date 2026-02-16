from aiida import orm

def get_bands_plot_data(pk):
    """
    Retrieve plotting data from a BandsData node.
    Returns a dictionary suitable for matplotlib plotting or None if not supported.
    """
    try:
        node = orm.load_node(pk)
        
        # 1. Try Fetching Raw Data via _matplotlib_get_dict (internal AiiDA method)
        if hasattr(node, '_matplotlib_get_dict'):
            return node._matplotlib_get_dict()
            
    except Exception as e:
        print(f"Error getting bands data for {pk}: {e}")
        return None
    
    return None
