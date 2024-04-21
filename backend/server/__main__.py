import os
import sys
import redis
import shutil
from dotenv import load_dotenv

from __init__ import run


load_dotenv("./.env")

HELP_STR = """
USAGE: python server <command>
COMMANDS:
    help: Displays this message
    run: Runs the server
    clearcache: Clears all the video cache and deletes them from filesystem
"""


def clear_cache():
    rclient = redis.from_url(os.environ["REDIS_URL"])
    keys = rclient.keys("videos:*")
    keys = [k.decode() for k in keys]

    for dir in os.listdir("videos"):
        if f"videos:{dir}" in keys:
            shutil.rmtree(f"videos/{dir}")

    rclient.delete(*keys)


if len(sys.argv) < 2:
    print(HELP_STR)
else:
    cmd = sys.argv[1]

    match cmd:
        case "help":
            print(HELP_STR)
        case "run":
            run()
        case "clearcache":
            clear_cache()
        case _:
            print(HELP_STR)
