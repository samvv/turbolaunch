
from collections.abc import Callable, Iterable, Sequence
import re
from typing import Generic, TextIO, TypeVar
from io import StringIO

def to_kebab_case(name: str) -> str:
    return name.replace('_', '-')


def to_snake_case(name: str) -> str:
    return name.replace('-', '_')


_T = TypeVar('_T')


class Peek(Generic[_T]):

    def __init__(self, iter: Iterable[_T]) -> None:
        self._elements = list(iter)
        self._offset = 0

    def get(self) -> _T | None:
        if self._offset >= len(self._elements):
            return None
        element = self._elements[self._offset]
        self._offset += 1
        return element

    def peek(self) -> _T | None:
        return self._elements[self._offset] if self._offset < len(self._elements) else None


def find(l: Sequence[_T], pred: Callable[[_T], bool]) -> int | None:
    for i, element in enumerate(l):
        if pred(element):
            return i


class IndentWriter:

    def __init__(self, out: TextIO | None = None, indentation='  '):
        if out is None:
            out = StringIO()
        self.output = out
        self.at_blank_line = True
        self.newline_count = 0
        self.indent_level = 0
        self.indentation = indentation
        self._re_whitespace = re.compile('[\n\r\t ]')

    def indent(self):
        self.indent_level += 1

    def dedent(self):
        self.indent_level -= 1

    def ensure_trailing_lines(self, count):
        self.write('\n' * max(0, count - self.newline_count))

    def write(self, text: str) -> None:
        for ch in text:
            if ch == '\n':
                self.newline_count = self.newline_count + 1 if self.at_blank_line else 1
                self.at_blank_line = True
            elif self.at_blank_line and not self._re_whitespace.match(ch):
                self.newline_count = 0
                self.output.write(self.indentation * self.indent_level)
                self.at_blank_line = False
            self.output.write(ch)

    def writeln(self, text: str = '') -> None:
        self.write(text)
        self.write('\n')

