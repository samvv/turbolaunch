TurboLaunch
===========

TurboLaunch is a CLI parser for Python programs that requires almost no setup.

 - ✅ Run Python functions directly as CLI commands
 - ✅ Support for enums and other built-in types
 - 🚧 Help messages derived from docstrings
 - 🚧 Plugins to extend the functionality of this library
 - 🚧 Fuzzing of as much code paths as possible to ensure quality

TurboLaunch was initially written as part of the [Mage project](https://github.com/samvv/mage).

## Quick Start

Simply create or edit a module with the following code:

```py
def main() -> int:
    import turbolaunch
    turbolaunch.launch('mylibrary.mainmodule')
```

In your `pyproject.toml`-file, you'd have something like this:

```toml
[project.scripts]
mycommand = "mylibrary:main"
```

That's it!

Now if you would like to have command `test` which e.g. takes a filename and an optional `foo` flag:

```py
def test(filename: str, foo: bool = False) -> int:
    if foo:
        print("'foo' is enabled")
    print(f"Reading {filename}")
    return 0
```

The above code would be run like this:

```
mycommand test --foo
```

More options, such as programmatic usage and plugins will come soon.

## License

This software is licensed under the MIT license.
