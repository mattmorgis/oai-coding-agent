from typing import Any, Callable, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

def Option(*args: Any, **kwargs: Any) -> Any: ...

class Typer:
    rich_markup_mode: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def command(self) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
