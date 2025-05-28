from typing import Any, Dict, Type

class Heading:
    text: Any
    def __rich_console__(self, console: Any, options: Any) -> Any: ...

class Markdown:
    elements: Dict[str, Type[Any]]

    def __init__(self, text: Any, code_theme: Any = ..., hyperlinks: Any = ...) -> None: ...
