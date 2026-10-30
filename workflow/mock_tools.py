def mock_calculator(inputs):
    a = inputs.get("a")
    b = inputs.get("b")

    if (
        not isinstance(a, (int, float))
        or isinstance(a, bool)
        or not isinstance(b, (int, float))
        or isinstance(b, bool)
    ):
        raise ValueError("Inputs a and b must be numbers")

    return {
        "tool": "mock_calculator",
        "result": a + b,
        "mode": "mock",
    }


def mock_note_preview(inputs):
    title = inputs.get("title", "")
    content = inputs.get("content", "")

    if not isinstance(title, str):
        raise ValueError("Title must be a string")

    if not isinstance(content, str):
        raise ValueError("Content must be a string")

    return {
        "tool": "mock_note_preview",
        "preview": f"{title}: {content}",
        "mode": "mock",
    }


MOCK_TOOLS = {
    "mock_calculator": mock_calculator,
    "mock_note_preview": mock_note_preview,
}