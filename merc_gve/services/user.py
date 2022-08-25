# coding: utf-8
import json
import os
import sys


class User:
    def __init__(self, file=None):
        self.username = None
        self.password = None

        if file is None:
            default_name = "user.json"
            current_dir = os.path.abspath(os.path.dirname(__file__))
            file_path = os.path.join(current_dir, default_name)

            if default_name in os.listdir(current_dir):
                self.read_user(file_path)
            else:
                self.create_file_user(file_path)
        else:
            current_dir = os.path.abspath(os.path.dirname(__file__))
            if file in os.listdir(current_dir):
                self.read_user(file)
            else:
                print(f"не найдено: {file}")
                self.create_file_user(file)

    def read_user(self, file):
        with open(file, "r") as f:
            sett = json.load(f)
        self.username = sett["j_username"]
        self.password = sett["j_password"]

    @staticmethod
    def create_file_user(file):
        with open(file, "w") as f:
            json.dump(
                dict(j_username="your_login", j_password="your_password"), f, indent=4
            )
        print(f"заполни {file} и запусти заного")
        sys.exit(0)
