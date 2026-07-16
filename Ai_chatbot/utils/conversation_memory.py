MAX_HISTORY = 8


def build_conversation(history):

    if history is None:
        return ""

    conversation = []

    for item in history[-MAX_HISTORY:]:

        role = item.get("role", "")

        content = item.get("content", "")

        if role == "user":
            conversation.append(
                f"User: {content}"
            )

        elif role == "assistant":
            conversation.append(
                f"Assistant: {content}"
            )

    return "\n".join(conversation)