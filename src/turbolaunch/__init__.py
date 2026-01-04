
from types import ModuleType

from .program import *
from .parse import parse
from .convert import convert, convert_command

class App:

    def __init__(self, name) -> None:
        self.program = Program(name)

    def command[F: Callable[..., int | None]](self, name: str | None = None) -> Callable[[F], F]:
        def decorator(f: F) -> F:
            self.program.add_subcommand(convert_command(f, name))
            return f
        return decorator

    def __call__(self, argv: list[str]) -> int | None:
        cmd, posargs, kwargs = parse(self.program, argv[1:])
        assert(cmd.callback is not None)
        return cmd.callback(*posargs, **kwargs)

def launch(mod: ModuleType | str, name: str | None = None) -> int:

    cmd, posargs, kwargs = parse(convert(mod, name=name))

    if cmd.callback is None:
        print('Command could not be executed. Perhaps you specified the wrong arguments?')
        return 1

    # Call the function in user-space
    return cmd.callback(*posargs, **kwargs)
