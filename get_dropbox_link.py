#!/usr/local/bin/python3
# coding=utf-8

# Copyright 2021 Nick Kocharhook
# MIT Licensed

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import dropbox
from dropbox.exceptions import ApiError

import argparse
from pathlib import Path as P
import sys
import json
import logging

# Add OAuth2 access token here.
# You can generate one for yourself in the App Console.
# See <https://blogs.dropbox.com/developers/2014/05/generate-an-access-token-for-your-own-account/>
TOKEN = ""

# Either 'personal' or 'business'. Must match the account which generated
# the TOKEN above.
# See <https://help.dropbox.com/installs-integrations/desktop/locate-dropbox-folder>
ACCOUNT_TYPE = "personal"


def main():
    local_dbx_path = None
    args = parseArguments()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    with dropbox.Dropbox(TOKEN) as dbx:
        try:
            dbx.users_get_current_account()
        except AuthError:
            sys.exit(
                "ERROR: Invalid access token; try re-generating an "
                "access token from the app console on the web."
            )

        try:
            with open(P.home() / ".dropbox/info.json") as jsonf:
                info = json.load(jsonf)
                local_dbx_path = info[ACCOUNT_TYPE]["path"]
        except Exception:
            logging.error("Couldn't find Dropbox folder path")
            sys.exit(1)

        for path in args.paths:
            try:
                p = P(path).absolute()
                logging.debug(f"Processing file at path {p}")
                relp = p.relative_to(local_dbx_path)
                dbx_path = f"/{relp}"
            except Exception as e:
                logging.error(str(e))
                sys.exit(1)

            try:
                link = dbx.sharing_create_shared_link(dbx_path)
                print(link.url)
            except ApiError as e:
                logging.error(str(e))
                sys.exit(1)


def parseArguments():
    parser = argparse.ArgumentParser(description="Fetch Dropbox URL for path")
    parser.add_argument("paths", type=str, nargs="+", help="paths to files")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="toggle verbose mode"
    )

    args = parser.parse_args()

    return args


if __name__ == "__main__":
    main()
