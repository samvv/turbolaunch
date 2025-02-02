
from types import ModuleType as _ModuleType
from .program import *
from .parse import parse
from .convert import convert

def launch(mod: _ModuleType | str, name: str | None = None) -> int:

    cmd, posargs, kwargs = parse(convert(mod, name=name))

    if cmd.callback is None:
        print('Command could not be executed. Perhaps you specified the wrong arguments?')
        return 1

    # Call the function in user-space
    return cmd.callback(*posargs, **kwargs)
