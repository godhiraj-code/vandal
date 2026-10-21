"""Export only bounded regular output files; never follow a candidate's symlink."""
import io
import os
import stat
import sys
import tarfile
from pathlib import Path

NAMES = ("worker-status.json", "venv.log", "install.log", "environment.txt", "baseline.log",
         "baseline.xml", "mutation.log", "vandal_report.json")


def main():
    total = 0
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        for name in NAMES:
            try:
                fd = os.open(Path("/work/out") / name, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                continue
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 8 * 1024 * 1024:
                    raise ValueError("nonregular or oversized artifact")
                data = stream.read(8 * 1024 * 1024 + 1)
            total += len(data)
            if total > 32 * 1024 * 1024:
                raise ValueError("artifact total exceeds limit")
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


if __name__ == "__main__":
    main()
