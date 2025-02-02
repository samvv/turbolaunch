"""
Convert a list of arguments to a function that is ready to be invoked
"""
from enum import Enum, IntEnum, StrEnum
from collections.abc import Iterable
from pathlib import Path
import sys
from types import UnionType
from typing import Any, Literal, TypeAliasType
import typing

from .program import ArgValues, Command, Program
from .types import get_cls, has_type
from .util import Peek, find, to_snake_case

class CLIError(RuntimeError):
    pass

class ValueParseError(CLIError):

    def __init__(self, text: str) -> None:
        super().__init__(f"failed to parse {repr(text)} as a value")

class ValueMissingError(CLIError):

    def __init__(self, name: str) -> None:
        super().__init__(f"value missing for argument '{name}'")

class UnknownArgError(CLIError):

    def __init__(self, arg: str) -> None:
        super().__init__(f"unknown argument received: '{arg}'")

def _try_parse_value(text: str, types: Iterable[Any]) -> Any:
    for ty_2 in types:
        try:
            return _parse_value(text, ty_2)
        except ValueParseError:
            pass
    raise ValueParseError(f'unable to parse as any of {types}')

def _parse_value(text: str, ty: Any) -> Any:
    if isinstance(ty, TypeAliasType):
        assert(not ty.__type_params__)
        ty = ty.__value__
    origin = typing.get_origin(ty)
    if origin is UnionType:
        args = typing.get_args(ty)
        return _try_parse_value(text, args)
    if origin is Literal:
        args = typing.get_args(ty)
        for arg in args:
            try:
                value = _parse_value(text, get_cls(arg))
            except ValueParseError:
                continue
            if value != arg:
                return value
        raise ValueParseError(f"no literal types matched")
    if ty is Path:
        return Path(text)
    if ty is float:
        try:
            return float(text)
        except ValueError:
            raise ValueParseError(text)
    if ty is str:
        return text
    if ty is Any:
        return _try_parse_value(text, [ bool, int, float, str ])
    if ty is bool:
        if text in [ 'on', 'true', '1' ]:
            return True
        if text in [ 'off', 'false', '0' ]:
            return False
        raise ValueParseError(text)
    if ty is int:
        try:
            return int(text)
        except ValueError:
            raise ValueParseError(text)
    if issubclass(ty, StrEnum):
        try:
            return ty(text)
        except ValueError:
            raise ValueParseError(text)
    if issubclass(ty, IntEnum):
        try:
            return ty(int(text)) # type: ignore
        except ValueError:
            raise ValueParseError(text)
    raise RuntimeError(f'parsing the given value according to {ty} is not supported')

def _get_type_default(ty: Any) -> Any:
    if isinstance(ty, Enum):
        if hasattr(ty, '_default_'):
            return getattr(ty, '_default_')

def parse(prog: Program) -> tuple[Command, list[Any], dict[str, Any]]:

    # Variables used during processing of the arguments
    cmd = prog
    args = Peek(sys.argv[1:])
    mapping: ArgValues = {}
    pos_index = 0
    pos_arg_count = 0

    # Process arguments one by one
    while True:

        arg = args.get()

        if arg is None:
            break # We're at the end of the arguments list

        if arg.startswith('-'): # We're dealing with a flag

            i = find(arg, lambda ch: ch != '-')

            if i is None:
                raise UnknownArgError(arg)

            try:
                j = arg.index('=', i)
                name = to_snake_case(arg[i:j])
                value_str = arg[j+1:]
            except ValueError:
                name = to_snake_case(arg[i:])
                value_str = None

            arg_desc = cmd.get_flag(name)

            if arg_desc is None:
                arg_desc = cmd.rest_flags_argument
                if arg_desc is None:
                    raise UnknownArgError(arg)

            ty = arg_desc.ty

            value = None

            if value_str is not None:
                value = _parse_value(value_str, ty)
            else:
                # `value` is still `None` here
                next_arg = args.peek()
                if next_arg is not None and not next_arg.startswith('-'):
                    try:
                        value = _parse_value(next_arg, ty)
                        args.get()
                    except ValueParseError:
                        pass # `value` remains `None` and lookahead is discarded

            if value is None:
                if has_type(arg_desc.ty, bool) or arg_desc.is_rest_flags:
                    # Assume `True` in the cases where a boolean is expected or
                    # when it could potentially be a boolean but we don't know
                    # for sure
                    value = True
                elif arg_desc.default is not None:
                    # For all types except bool, attempt to assign the default
                    # value of the flag.
                    value = arg_desc.default
                else:
                    # If the user didn't explicitly specify a default, maybe we
                    # can derive a default from the type.
                    default = _get_type_default(arg_desc.ty)
                    if default is not None:
                        value = default
                    elif arg_desc.min_count > 0: # If the flag was required
                        raise ValueMissingError(name)

            arg_desc.parse_callback(name, value, mapping)

        else: # We're dealing with a positional argument

            # Try to parse the argument as a subcommand first
            subcmd = cmd.get_subcommand(arg)
            if subcmd is not None:
                cmd = subcmd
                pos_index = 0
                pos_arg_count = 0
                continue

            # If that fails, process it as a plain positional argument

            while True:
                if pos_index >= len(cmd._pos_args):
                    raise UnknownArgError(arg)
                arg_desc = cmd._pos_args[pos_index]
                if pos_arg_count >= arg_desc.max_count:
                    pos_index += 1
                    pos_arg_count = 0
                    continue
                value = _parse_value(arg, arg_desc.ty)
                arg_desc.parse_callback(arg_desc.name, value, mapping)
                pos_arg_count += 1
                break

    # TODO check that required arguments have been set

    # Build positional arguments and keyword arguments from the mapping
    posargs = []
    kwargs = {}
    for name, value in mapping.items():
        arg_desc = cmd.get_argument(name)
        assert(arg_desc is not None)
        if arg_desc.is_positional:
            if arg_desc.is_rest_pos:
                posargs.extend(value)
            else:
                posargs.append(value)
        else:
            if arg_desc.is_rest_flags:
                kwargs.update(value)
            else:
                kwargs[name] = value

    return cmd, posargs, kwargs

