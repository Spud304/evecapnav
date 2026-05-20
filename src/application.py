import os

from flask import Flask, send_from_directory


class Application(Flask):
    def __init__(self, import_name, **kwargs):
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        kwargs.setdefault("static_folder", static_dir)
        kwargs.setdefault("static_url_path", "")
        super().__init__(import_name, **kwargs)
        self._add_routes()

    def _add_routes(self):
        self.add_url_rule("/", "index", self.index, methods=["GET"])
        self.add_url_rule("/health", "health", self.health, methods=["GET"])

    def index(self):
        # static_folder is always set in __init__; assert for the type checker.
        assert self.static_folder is not None
        return send_from_directory(self.static_folder, "index.html")

    def health(self) -> str:
        return "OK"
