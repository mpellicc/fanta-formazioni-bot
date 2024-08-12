def default_response_handler(text: str) -> str:
    """Utility method to test the bot activeness."""
    processed: str = text.lower()

    if "ciao" in processed:
        return "Ciao!"

    return "Non capisco..."
