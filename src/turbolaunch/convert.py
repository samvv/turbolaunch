
import inspect
from pathlib import Path
import sys
from types import ModuleType
import typing

from turbolaunch.types import describe_type

from .program import *
from .util import IndentWriter, to_kebab_case

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
