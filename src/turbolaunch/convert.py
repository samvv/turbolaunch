
import inspect
from pathlib import Path
import sys
from types import ModuleType
import typing

from turbolaunch.constants import FALSE_MEMBER_NAME, TRUE_MEMBER_NAME
from turbolaunch.types import describe_type

from .program import *
from .util import IndentWriter, ident, is_boolish, to_kebab_case

def _inserter(name: str) -> ArgFn:
    def func(key: str, value: Any, out: ArgValues) -> None:
        if name not in out:
            m = {}
            out[name] = m
        else:
            m = out[name]
        m[key] = value
    return func

def _append(name: str, value: Any, out: ArgValues) -> None:
    if not name in out:
        out[name] = []
    out[name].append(value)

def _print_help_loop(cmd: Command, out: IndentWriter, depth: int) -> None:
    out.write(f'{cmd.name}')
    if cmd.description is not None:
        out.write('    ')
        out.write(cmd.description)
    out.writeln()
    out.indent()
    if cmd.count_arguments() > 0 and depth == 0:
        out.writeln('Arguments and flags:')
        for arg in cmd.arguments():
            if arg.is_flag:
                if len(arg.name) == 1:
                    out.write(f'-{arg.name}')
                else:
                    out.write(f'--{arg.name}')
            elif arg.min_count == 0:
                if arg.max_count == 1:
                    out.write(f'[{arg.name}]')
                else:
                    out.write(f'[{arg.name}..]')
            else:
                if arg.max_count == 1:
                    out.write(f'<{arg.name}>')
                else:
                    out.write(f'<{arg.name}..>')
            out.write('    ')
            out.write(describe_type(arg.ty))
            out.writeln()
    if cmd.count_subcommands() > 0:
        out.writeln('\nSubcommands:')
        out.indent()
        for sub in cmd.subcommands():
            _print_help_loop(sub, out, depth+1)
        out.dedent()
    out.dedent()

def _print_help(cmd: Command) -> None:
    out = IndentWriter(sys.stderr)
    _print_help_loop(cmd, out, 0)
    exit(1)

def convert(mod: ModuleType | str, name: str | None = None) -> Program:

    if name is None:
        name = Path(sys.argv[0]).stem

    if isinstance(mod, str):
        import importlib
        mod = importlib.import_module(mod)

    prog = Program(name)

    for name, proc in mod.__dict__.items():

        if not name.startswith('_') and callable(proc) and proc.__module__ == mod.__name__:

            try:
                sig = inspect.signature(proc)
            except ValueError:
                continue

            cmd = Command(to_kebab_case(name))

            types = typing.get_type_hints(proc)

            for name, param in sig.parameters.items():

                ty = types[param.name]

                arg = Argument(name)

                arg.set_type(ty)

                if param.default is not param.empty:
                    arg.set_default(param.default)
                    arg.set_optional()

                if param.kind == param.POSITIONAL_ONLY or param.kind == param.POSITIONAL_OR_KEYWORD or param.kind == param.VAR_POSITIONAL:
                    arg.set_positional()
                if param.kind == param.KEYWORD_ONLY or param.kind == param.POSITIONAL_OR_KEYWORD or param.kind == param.VAR_KEYWORD:
                    arg.set_flag()

                if param.kind == param.VAR_KEYWORD:
                    if typing.get_origin(ty) is typing.Unpack:
                        args = typing.get_args(ty)
                        total = args[0].__total__
                        for k, v in typing.get_type_hints(args[0]).items():
                            arg = Argument(k)
                            arg.set_flag()
                            required = True
                            if typing.get_origin(v) is typing.NotRequired:
                                required = False
                                v = typing.get_args(v)[0]
                            arg.set_type(v)
                            if not total or not required:
                                arg.set_optional()
                            cmd.add_argument(arg)
                        continue
                    else:
                        arg.set_rest()
                        arg.set_callback(_inserter(name))
                if param.kind == param.VAR_POSITIONAL:
                    arg.set_rest()
                    arg.set_no_max_count()
                    arg.set_callback(_append)

                cmd.add_argument(arg)

            cmd.set_callback(proc)

            help_arg = Argument('help')
            help_arg.set_flag()
            help_arg.set_type(bool)
            help_arg.set_callback(lambda key, value, out, cmd=cmd: _print_help(cmd))
            cmd.add_argument(help_arg)

            prog.add_subcommand(cmd)

    help_arg = Argument('help')
    help_arg.set_flag()
    help_arg.set_type(bool)
    help_arg.set_callback(lambda key, value, out: _print_help(prog))
    prog.add_argument(help_arg)

    add_complements(prog)

    return prog

def _boolish_setter(map: Callable[[Any], bool], name: str, inverted: bool = False) -> ArgFn:
    def func(_: str, value: Any, out: ArgValues) -> None:
        out[name] = map(value != inverted)
    return func

def _bool_to_boolish_fn(ty: Any) -> Callable[[Any], bool]:
    if ty is bool:
        return ident
    if hasattr(ty, TRUE_MEMBER_NAME) and hasattr(ty, FALSE_MEMBER_NAME):
        return lambda x: getattr(ty, TRUE_MEMBER_NAME) if x else getattr(ty, FALSE_MEMBER_NAME)
    raise ValueError(f'{ty} is not a valid boolean-like type')

def add_complements(prog: Program) -> None:
    """
    Generates additional arguments that are the inverse of existing arguments.

    Example: `--enable-foo` will ackquire `--disable-foo` and both will work.

    Two additional flags can also be enabled that enable/disable all flags at once.

    Example: `--enable-all` and `--disable-all`
    """

    def visit(cmd: Command) -> None:

        enable_flags = list[tuple[str, Callable[[Any], bool]]]()
        disable_flags = list[tuple[str, Callable[[Any], bool]]]()

        for arg in list(cmd.arguments()):
            if not arg.is_rest and is_boolish(arg.ty):
                if arg.name.startswith('enable_'):
                    suffix = arg.name[7:]
                    map = _bool_to_boolish_fn(arg.ty)
                    enable_flags.append((arg.name, map))
                    arg.set_callback(_boolish_setter(map, arg.name))
                    inv_arg = Argument('disable_' + suffix)
                    inv_arg.set_callback(_boolish_setter(map, arg.name, inverted=True))
                    inv_arg.set_optional()
                    inv_arg.set_type(arg.ty)
                    inv_arg.set_flag()
                    cmd.add_argument(inv_arg)
                elif arg.name.startswith('disable_'):
                    suffix = arg.name[8:]
                    map = _bool_to_boolish_fn(arg.ty)
                    disable_flags.append((arg.name, map))
                    arg.set_callback(_boolish_setter(map, arg.name))
                    inv_arg = Argument('enable_' + suffix)
                    inv_arg.set_optional()
                    inv_arg.set_flag()
                    inv_arg.set_type(arg.ty)
                    inv_arg.set_callback(_boolish_setter(map, arg.name, inverted=True))
                    cmd.add_argument(inv_arg)

        if enable_flags or disable_flags:
            enable_all = Argument('enable_all')
            enable_all.set_flag()
            enable_all.set_optional()
            enable_all.set_type(bool)
            def enable_all_cb(_: str, value: bool, out: ArgValues) -> None:
                for name, map in enable_flags:
                    out[name] = map(value)
                for name, map in disable_flags:
                    out[name] = map(not value)
            enable_all.set_callback(enable_all_cb)
            cmd.add_argument(enable_all)
            disable_all = Argument('disable_all')
            disable_all.set_flag()
            disable_all.set_optional()
            disable_all.set_type(bool)
            def disble_all_cb(_: str, value: bool, out: ArgValues) -> None:
                for name, map in disable_flags:
                    out[name] = map(value)
                for name, map in disable_flags:
                    out[name] = map(not value)
            disable_all.set_callback(disble_all_cb)
            cmd.add_argument(disable_all)

        for subcmd in cmd.subcommands():
            visit(subcmd)

    visit(prog)

