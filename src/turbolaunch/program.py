
from collections.abc import Callable, Iterable
from typing import Any
import math

type ArgValue = Any

type ArgValues = dict[str, ArgValue]

type ArgFn = Callable[[str, ArgValue, ArgValues], None]

ARGFLAGS_FLAG = 1
ARGFLAGS_POSITIONAL = 2
ARGFLAGS_REST = 4

def _set_arg_value(name: str, value: Any, out: ArgValues) -> None:
    out[name] = value

def _bool_setter(name: str, inverted: bool = False) -> ArgFn:
    def func(_: str, value: Any, out: ArgValues) -> None:
        out[name] = value != inverted
    return func

def _are_bits_set(mask: int, bit: int) -> bool:
    return mask & bit == bit

def _set_bit(mask: int, bit: int, enable: bool) -> int:
    if enable:
        return mask | bit
    else:
        return mask & ~bit

class Argument:

    def __init__(self, name: str) -> None:
        self.name = name
        self.flags = 0
        self.ty: Any = None
        self.min_count = 1
        self.max_count = 1
        self.default: ArgValue | None = None
        self.parse_callback: ArgFn = _set_arg_value

    @property
    def is_positional(self) -> bool:
        return (self.flags & ARGFLAGS_POSITIONAL) > 0

    @property
    def is_flag(self) -> bool:
        return (self.flags & ARGFLAGS_FLAG) > 0

    @property
    def is_rest(self) -> bool:
        return _are_bits_set(self.flags, ARGFLAGS_REST)

    @property
    def is_rest_flags(self) -> bool:
        return _are_bits_set(self.flags, ARGFLAGS_FLAG | ARGFLAGS_REST)

    @property
    def is_rest_pos(self) -> bool:
        return _are_bits_set(self.flags, ARGFLAGS_POSITIONAL | ARGFLAGS_REST)

    @property
    def is_optional(self) -> bool:
        return self.min_count == 0

    def set_flag(self, enable = True) -> None:
        self.flags = _set_bit(self.flags, ARGFLAGS_FLAG, enable)

    def set_rest(self, enable = True) -> None:
        self.flags = _set_bit(self.flags, ARGFLAGS_REST, enable)

    def set_positional(self, enable = True) -> None:
        self.flags = _set_bit(self.flags, ARGFLAGS_POSITIONAL, enable)

    def set_default(self, value: ArgValue) -> None:
        self.default = value

    def set_no_max_count(self) -> None:
        self.max_count = math.inf

    def set_type(self, ty: Any) -> None:
        self.ty = ty

    def set_optional(self) -> None:
        self.min_count = 0

    def set_required(self) -> None:
        if self.min_count == 0:
            self.min_count = 1

    def set_callback(self, cb: ArgFn) -> None:
        self.parse_callback = cb

class Command:

    def __init__(self, name: str) -> None:
        self.name = name
        self.description: str | None = None
        self.callback: Callable[..., int] | None = None
        self._subcommands = dict[str, Command]()
        self._arguments = dict[str, Argument]()
        self._pos_args: list[Argument] = []
        self._rest_flags_argument = None
        # self._arguments_by_flag = dict[str, Argument]()

    def arguments(self) -> Iterable[Argument]:
        return self._arguments.values()

    def subcommands(self) -> 'Iterable[Command]':
        return self._subcommands.values()

    def add_subcommand(self, cmd: 'Command') -> None:
        """
        Add a subcommand to this command.

        This class expects the command to not be mutated anymore after it has been added.
        """
        assert(cmd.name not in self._subcommands)
        self._subcommands[cmd.name] = cmd

    def count_arguments(self) -> int:
        return len(self._arguments)

    def add_argument(self, arg: Argument) -> None:
        """
        Add an argument to this command.

        This class expects the argument to not be mutated anymore after it has been added.
        """
        assert(arg.name not in self._arguments)
        self._arguments[arg.name] = arg
        if arg.is_positional:
            self._pos_args.append(arg)
        if arg.is_rest_flags:
            assert(self._rest_flags_argument is None)
            self._rest_flags_argument = arg

    @property
    def rest_flags_argument(self) -> Argument | None:
        return self._rest_flags_argument

    def set_callback(self, callback: Callable[..., Any]) -> None:
        self.callback = callback

    def get_argument(self, name: str) -> Argument | None:
        return self._arguments.get(name)

    def count_subcommands(self) -> int:
        return len(self._subcommands)

    def get_flag(self, name: str) -> Argument | None:
        arg = self.get_argument(name)
        if arg is not None and arg.is_flag:
            return arg

    def get_subcommand(self, name: str) -> 'Command | None':
        return self._subcommands.get(name)

class Program(Command):
    pass



def add_complements(prog: Program) -> None:
    """
    Generates additional arguments that are the inverse of existing arguments.

    Example: `--enable-foo` will ackquire `--disable-foo` and both will work.

    Two additional flags can also be enabled that enable/disable all flags at once.

    Example: `--enable-all` and `--disable-all`
    """

    def visit(cmd: Command) -> None:

        enable_flags = []
        disable_flags = []

        for arg in list(cmd.arguments()):
            if not arg.is_rest and arg.ty is bool:
                if arg.name.startswith('enable_'):
                    suffix = arg.name[7:]
                    enable_flags.append(arg.name)
                    arg.set_callback(_bool_setter(arg.name))
                    inv_arg = Argument('disable_' + suffix)
                    inv_arg.set_callback(_bool_setter(arg.name, inverted=True))
                    inv_arg.set_optional()
                    inv_arg.set_type(bool)
                    inv_arg.set_flag()
                    cmd.add_argument(inv_arg)
                elif arg.name.startswith('disable_'):
                    suffix = arg.name[8:]
                    disable_flags.append(arg.name)
                    arg.set_callback(_bool_setter(arg.name))
                    inv_arg = Argument('enable_' + suffix)
                    inv_arg.set_optional()
                    inv_arg.set_flag()
                    inv_arg.set_type(bool)
                    inv_arg.set_callback(_bool_setter(arg.name, inverted=True))

        if enable_flags or disable_flags:
            enable_all = Argument('enable_all')
            enable_all.set_flag()
            enable_all.set_optional()
            enable_all.set_type(bool)
            def enable_all_cb(_: str, value: bool, out: ArgValues) -> None:
                for name in enable_flags:
                    out[name] = value
                for name in disable_flags:
                    out[name] = not value
            enable_all.set_callback(enable_all_cb)
            cmd.add_argument(enable_all)
            disable_all = Argument('disable_all')
            disable_all.set_flag()
            disable_all.set_optional()
            disable_all.set_type(bool)
            def disble_all_cb(_: str, value: bool, out: ArgValues) -> None:
                for name in disable_flags:
                    out[name] = value
                for name in disable_flags:
                    out[name] = not value
            disable_all.set_callback(disble_all_cb)
            cmd.add_argument(disable_all)

        for subcmd in cmd.subcommands():
            visit(subcmd)

    visit(prog)

