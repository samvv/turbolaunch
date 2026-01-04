
import pytest
from turbolaunch import App

def test_simple_arg():
    app = App('myprog')
    _bla = None
    @app.command()
    def foo(bla: str) -> None:
        nonlocal _bla
        _bla = bla
    app([ 'myprog', 'foo', 'hello' ])
    assert(_bla == 'hello')

def test_simple_arg_2():
    app = App('myprog')
    _bla = None
    @app.command(name='bar')
    def foo(bla: str) -> None:
        nonlocal _bla
        _bla = bla
    with pytest.raises(RuntimeError):
        app([ 'myprog', 'foo', 'hello' ])
    app([ 'myprog', 'bar', 'hello' ])
    assert(_bla == 'hello')
