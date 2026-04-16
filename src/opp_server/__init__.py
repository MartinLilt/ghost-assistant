"""opp_server package."""

__all__ = ["greet"]


def greet(name: str = "world") -> str:
    return f"Hello, {name}!"

