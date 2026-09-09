"""Witdem + Onyx agency demo package."""

__all__ = ["create_client"]


def __getattr__(name: str):
    if name == "create_client":
        from witdem_onyx_demo.instrument import create_client

        return create_client
    raise AttributeError(name)
