import inspect
import os
import stat
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class Command(Enum):
    ECHO = "echo"
    CD = "cd"
    PWD = "pwd"
    LS = "ls"
    EXIT = "exit"
    CLEAR = "clear"
    HISTORY = "history"


class LsArguments(Enum):
    L = "l"
    A = "a"

    @classmethod
    def values(cls):
        return list(cls._value2member_map_.keys())


class Permissions:
    OWNER = [stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR]
    GROUP = [stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP]
    OTHERS = [stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH]


class History:
    HISTORY_FILE_PATH = "./.history_shell"

    @classmethod
    def init(cls):
        open(cls.HISTORY_FILE_PATH, "a").close()

    @classmethod
    def write_history(cls, source_command: str) -> None:
        with open(cls.HISTORY_FILE_PATH, "a") as history:
            history.write(f"{datetime.now().timestamp()}:{source_command}\n")
            history.flush()

    @classmethod
    def is_not_equal_last_history_record(cls, source_command: str) -> bool:
        if os.stat(cls.HISTORY_FILE_PATH).st_size == 0 or not source_command:
            return True

        with open(cls.HISTORY_FILE_PATH, "rb") as history:
            try:
                history.seek(-2, os.SEEK_END)
                while history.read(1) != b"\n":
                    history.seek(-2, os.SEEK_CUR)
            except OSError:
                history.seek(0)
            return history.readline().decode().split(":")[1].strip() != source_command

    @classmethod
    def show(cls):
        with open(cls.HISTORY_FILE_PATH, "r") as history:
            for index, value in enumerate(history.readlines()):
                print(f"{index}  {value.split(':')[1].strip()}")


class Parser:
    def __init__(self, source_command: str) -> None:
        self.tokens = self._tokenize(source_command)
        self.main_command = self._parse_main_command()
        self.arguments = self.tokens[1:]

    def _parse_main_command(self) -> Optional[str]:
        if self.tokens:
            main_command = self.tokens[0]
            try:
                self._validate_main_command(main_command)
                return main_command
            except ValueError:
                print(f"Command not found: {main_command}")
        return None

    def _validate_main_command(self, main_command: str) -> None:
        if main_command.upper() not in Command._member_names_:
            raise ValueError("Commands not found.")

    @staticmethod
    def _tokenize(source_command: str) -> list[str]:
        return source_command.split()


PERMISSIONS_SYMBOLS = ["r", "w", "x"]
EMPTY_PERMISSION_SYMBOL = "-"


class CommandManager:
    def __init__(self, parser: Parser) -> None:
        self._main_command = parser.main_command
        self._arguments = parser.arguments

    def run(self) -> Callable[[Optional[list[str]]], None]:
        if self._main_command and hasattr(self, self._main_command):
            return self._execute_command()
        return None

    def _execute_command(self) -> Callable[[Optional[list[str]]], None]:
        method = getattr(self, self._main_command)

        if self._arguments and self._able_to_receive_arguments(method):
            return method(self._arguments)
        return method()

    @staticmethod
    def _able_to_receive_arguments(
        method: Callable[[Optional[list[str]]], None]
    ) -> list[str]:
        return inspect.getfullargspec(method).args

    def echo(self, arguments: list[str] = []) -> None:
        args = arguments if arguments else self._arguments
        print(" ".join(str(arg) for arg in args))

    @staticmethod
    def exit() -> None:
        exit(0)

    @staticmethod
    def clear() -> None:
        os.system("clear")

    @staticmethod
    def pwd() -> None:
        print(Path.cwd())

    @staticmethod
    def history():
        History.show()

    def cd(self, argument_path: list[str] = []) -> None:
        path = "".join(argument_path) if argument_path else str(Path.home())
        try:
            os.chdir(os.path.abspath(path))
            self.pwd()
        except FileNotFoundError:
            print(f"cd: no such file or directory: {path}")

    def ls(self, parameters: list[str] = []) -> None:
        arguments = set(parameters)
        try:
            ls_args, path = self._parse_ls_arguments(arguments)
            if not ls_args or LsArguments.A.value not in ls_args:
                no_hidden_items = self._get_no_hidden_items_from_path(path)
                for path_item in no_hidden_items:
                    if LsArguments.L.value in ls_args:
                        print(self._format_ls_long_listing(path_item))
                    else:
                        print(path_item.name)
            else:
                for path_item in path.iterdir():
                    if LsArguments.L.value in ls_args:
                        print(self._format_ls_long_listing(path_item))
                    else:
                        print(path_item.name)
        except ValueError as e:
            print(e)

    def _parse_ls_arguments(self, arguments: set[str]) -> tuple[list[str], Path]:
        ls_args = []
        path = Path.cwd()
        for argument in arguments:
            if argument.startswith("-"):
                ls_args = list(argument)[1:]
            else:
                path = self._validate_ls_path_argument(argument)
        return ls_args, path

    def _format_ls_long_listing(self, path_item: Path) -> str:
        stats = path_item.stat()
        return (
            f"{self._format_path_permissions_levels(stats.st_mode)} "
            f"{stats.st_nlink} {path_item.owner()} {path_item.group()}  "
            f"{stats.st_size} {datetime.fromtimestamp(stats.st_ctime)} {path_item.name}"
        )

    def _format_path_permissions_levels(self, st_mode: int) -> str:
        permissitons = "d" if stat.S_ISDIR(st_mode) else "-"
        permissitons = self._format_owner_permissions(permissitons, st_mode)
        permissitons = self._format_group_permissions(permissitons, st_mode)
        permissitons = self._format_others_permissions(permissitons, st_mode)

        return permissitons

    @staticmethod
    def _format_owner_permissions(permissions: str, st_mode: int):
        for index, value in enumerate(Permissions.OWNER):
            if bool(st_mode & value):
                permissions += PERMISSIONS_SYMBOLS[index]
            else:
                permissions += EMPTY_PERMISSION_SYMBOL
        return permissions

    @staticmethod
    def _format_group_permissions(permissions: str, st_mode: int) -> str:
        for index, value in enumerate(Permissions.GROUP):
            if bool(st_mode & value):
                permissions += PERMISSIONS_SYMBOLS[index]
            else:
                permissions += EMPTY_PERMISSION_SYMBOL
        return permissions

    @staticmethod
    def _format_others_permissions(permissions: str, st_mode: int) -> str:
        for index, value in enumerate(Permissions.OTHERS):
            if bool(st_mode & value):
                permissions += PERMISSIONS_SYMBOLS[index]
            else:
                permissions += EMPTY_PERMISSION_SYMBOL
        return permissions

    @staticmethod
    def _get_no_hidden_items_from_path(path: Path) -> list[Path]:
        return [
            path_item
            for path_item in path.iterdir()
            if not path_item.name.startswith(".")
        ]

    @staticmethod
    def _validate_ls_path_argument(path_argument: str) -> Path:
        path = Path(path_argument)
        if path.exists():
            return path
        raise ValueError(
            f"ls: cannot access '{path_argument}': No such file or directory"
        )


def main() -> None:
    History().init()
    while True:
        source_command = input("% ")
        parser = Parser(source_command)
        command_manager = CommandManager(parser)
        command_manager.run()

        if History.is_not_equal_last_history_record(source_command):
            History.write_history(source_command)


if __name__ == "__main__":
    main()
