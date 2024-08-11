import logging

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def handle_response(text: str) -> str:
    """Utility method to test the bot activeness."""
    processed: str = text.lower()

    if "ciao" in processed:
        return "Ciao!"

    return "Non capisco..."
