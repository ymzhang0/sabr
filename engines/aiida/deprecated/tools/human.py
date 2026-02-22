def ask_human(question: str):
    """
    Ask the human user a question when you are stuck or need more information (e.g., missing PK, clarification on group name).
    The execution will pause until the user replies in the next turn.
    
    Args:
        question (str): The question to ask the user.
    """
    # We return a specific formatted string that the Agent Loop can detect if we want special handling,
    # or simply rely on the LLM to relay it.
    # By returning this, the LLM will likely output: "I have asked the user..." and stop.
    return f"[WAITING FOR HUMAN INPUT] Question: {question}"
