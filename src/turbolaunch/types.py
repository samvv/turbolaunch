
from collections.abc import Generator
import types
import typing
from typing import Any, Union


def describe_type(ty: Any) -> str:
    if type(ty) is typing.TypeAliasType:
        return describe_type(ty.__value__)
    origin = typing.get_origin(ty)
    if origin is None:
        return ty.__name__
    elif origin is typing.Union or origin is types.UnionType:
        return ' | '.join(describe_type(arg) for arg in typing.get_args(ty))
    elif origin is typing.Literal:
        return ' | '.join(repr(lit) for lit in typing.get_args(ty))
    else:
        raise NotImplementedError(f"{ty} cannot be printed yet")


def is_optional(ty: Any) -> bool:
    origin = typing.get_origin(ty)
    if origin is types.UnionType:
        args = typing.get_args(ty)
        for arg in args:
            if arg is None:
                return True
    return False


def unwrap_optional(ty: Any) -> Any:
    origin = typing.get_origin(ty)
    if origin is types.UnionType:
        args = typing.get_args(ty)
        return Union[*(arg for arg in args if arg is not None)]
    return ty


def get_cls(value: Any) -> Any:
    return value.__class__


def flatten_union_type(ty: Any) -> Generator[Any]:
    origin = typing.get_origin(ty)
    if origin is typing.Union or origin is types.UnionType:
        for arg in typing.get_args(ty):
            yield from flatten_union_type(arg)
    else:
        yield ty


def has_type(left: Any, right: Any) -> bool:
    """
    Check whether `right` occurs somewhere in `left`.

    For instance:
    has_type(int | bool | str, bool) == True
    has_type(int | bool | str, float) == False
    """
    return right in flatten_union_type(left)

