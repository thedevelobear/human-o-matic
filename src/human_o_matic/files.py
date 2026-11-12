"""Writing a file whole: its bytes go to a hidden temporary file in its folder first, which then
takes its name, so no one ever reads half a file.

A new file takes its name by a hard link, which fails when the name is taken, so two writers never
share one (`name_new`). Where the file system has no hard links, as FAT, exFAT and some network
shares don't, the name is created exclusively and the bytes copied in: a taken name is still
refused, and a failed copy removes the file it began, but a process killed during the copy can
leave it short. A file that may exist is replaced with `os.replace`, which is whole too. A
temporary file is left behind only when the process is killed between writing it and naming it.
"""

import os
import tempfile
from pathlib import Path


def write_aside(folder: Path, data: bytes, *, prefix: str = ".") -> Path:
    """A hidden temporary file in `folder`, holding `data` whole."""
    with tempfile.NamedTemporaryFile(
        dir=folder, prefix=prefix, suffix=".tmp", delete=False
    ) as file:
        try:
            file.write(data)
        except BaseException:
            file.close()
            Path(file.name).unlink()
            raise
    return Path(file.name)


def name_new(aside: Path, path: Path) -> None:
    """Give the file written aside a new name, `path`, as well as its own, which the caller
    removes. Raises `FileExistsError` when the name is taken."""
    try:
        os.link(aside, path)
    except OSError as error:
        if isinstance(error, FileExistsError):
            raise
        # No hard links here: create the name exclusively and copy the bytes in.
        data = aside.read_bytes()
        with path.open("xb") as file:
            try:
                file.write(data)
            except BaseException:
                file.close()
                path.unlink()
                raise
