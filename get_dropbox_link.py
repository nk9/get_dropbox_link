#!/usr/bin/python3
# coding=utf-8

# Copyright 2023 Nick Kocharhook
# MIT Licensed

# Version 2 - https://github.com/nk9/get_dropbox_link

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

import argparse
import json
import logging
import sys
import typing as t
import webbrowser
from dataclasses import dataclass
from datetime import datetime as dt
from pathlib import Path
from enum import IntEnum
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from urllib.parse import urlparse

import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect


class AccountType(IntEnum):
    PERSONAL = 1
    BUSINESS = 2


# This is the App Key, NOT an OAuth2 token. Find your app's key in the App Console.
# See the README.
APP_KEY = ""

# Either PERSONAL or BUSINESS. Must match the account which generated
# the APP_KEY above.
# See <https://help.dropbox.com/installs-integrations/desktop/locate-dropbox-folder>
ACCOUNT_TYPE = AccountType.PERSONAL

# ADVANCED SETTINGS (Leave these alone.)
# Path to save script configuration.
CONFIG_PATH = "~/.get_dropbox_link_conf.json"

# Number of concurrent requests to the Dropbox API.
MAX_WORKERS = 10


def main():
    args = parseArguments()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    config_path = Path(CONFIG_PATH).expanduser()
    fetcher = LinkFetcher(
        APP_KEY, config_path, ACCOUNT_TYPE, args.query, args.plus_for_space
    )
    fetcher.fetch(args.paths)


class LinkFetcher:
    def __init__(self, app_key, config_path, account_type, query, plus_for_space):
        self.app_key = app_key
        self.config = Config.with_path(config_path)
        self.account_type = account_type.name.lower()
        self.query = query
        self.plus_for_space = plus_for_space

    def fetch(self, paths):
        local_dbx_path = None
        refresh_token = self.get_refresh_token()

        with dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            oauth2_access_token=self.config.access_token,
            oauth2_access_token_expiration=self.config.access_token_expiration,
            app_key=self.app_key,
        ) as dbx:
            if (
                not self.config.access_token
                or self.config.access_token_expiration < dt.now()
            ):
                dbx.refresh_access_token()
                self.config.update_access_token(
                    dbx._oauth2_access_token, dbx._oauth2_access_token_expiration
                )

            try:
                with open(Path.home() / ".dropbox/info.json") as jsonf:
                    info = json.load(jsonf)
                    local_dbx_path = info[self.account_type]["path"]
                    logging.debug(f"{local_dbx_path=}")
            except Exception as e:
                logging.error(f"Couldn't find Dropbox folder path: {e}")
                sys.exit(1)

            processed = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                processed = executor.map(
                    self.fetch_link, paths, repeat(dbx), repeat(local_dbx_path)
                )

            for link in processed:
                print(link)

    def fetch_link(self, path, dbx, local_dbx_path):
        try:
            p = Path(path).resolve().absolute()
            logging.debug(f"Processing file at path {p}")
            relative_p = p.relative_to(local_dbx_path)
            dbx_path = f"/{relative_p}"
        except Exception as e:
            logging.error(str(e))
            sys.exit(1)

        try:
            logging.debug(f"Creating shared link for {dbx_path}")
            link = dbx.sharing_create_shared_link(dbx_path)
            url = urlparse(link.url)
            url = url._replace(query=self.query)

            if self.plus_for_space:
                path = Path(url.path)
                new_path = path.with_stem(path.stem.replace("%20", "+"))
                url = url._replace(path=str(new_path))

            return url.geturl()
        except Exception as e:
            logging.error(str(e))
            sys.exit(1)

    def get_refresh_token(self):
        # Check if the config contains a token
        refresh_token = self.config.refresh_token

        # If not, go through the auth flow
        if not refresh_token:
            auth_flow = DropboxOAuth2FlowNoRedirect(
                self.app_key, use_pkce=True, token_access_type="offline"
            )

            authorize_url = auth_flow.start()
            webbrowser.open(authorize_url)
            print("Refresh token not found. Let's generate a new one.")
            print("1. Go to: " + authorize_url)
            print('2. Click "Allow", etc. (You may need to log in first.)')
            print("3. Copy the authorization code.")
            auth_code = input("Enter the authorization code here: ").strip()

            try:
                oauth_result = auth_flow.finish(auth_code)

                self.config.refresh_token = oauth_result.refresh_token
                self.config.update_access_token(
                    oauth_result.access_token, oauth_result.expires_at
                )
            except Exception as e:
                logging.error(str(e))
                sys.exit(1)

        return refresh_token


@dataclass
class Config:
    path: Path
    refresh_token: t.Optional[str]
    access_token: t.Optional[str]
    access_token_expiration: dt = dt.now()

    def update_access_token(self, new_token, new_expiration):
        if (
            new_expiration != self.access_token_expiration
            or new_token != self.access_token
        ):
            self.access_token = new_token
            self.access_token_expiration = new_expiration
            self.save()

    def save(self):
        with open(self.path, "w") as config_f:
            json.dump(
                {
                    "refresh_token": self.refresh_token,
                    "access_token": self.access_token,
                    "access_token_expiration": self.access_token_expiration.isoformat(),
                },
                config_f,
            )

    @classmethod
    def from_dict(cls: t.Type["Config"], path: Path, obj: dict):
        expiration = dt.now()

        if expiration_str := obj.get("access_token_expiration"):
            expiration = dt.fromisoformat(expiration_str)

        return cls(
            path=path,
            refresh_token=obj.get("refresh_token"),
            access_token=obj.get("access_token"),
            access_token_expiration=expiration,
        )

    @classmethod
    def with_path(cls, path: Path):
        try:
            with open(path) as config_f:
                return Config.from_dict(path, json.load(config_f))
        except:
            # If the file doesn't exist yet, or doesn't contain JSON
            return Config(path, None, None)


def parseArguments():
    parser = argparse.ArgumentParser(description="Fetch Dropbox URL for path")
    parser.add_argument("paths", type=str, nargs="+", help="paths to files")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="toggle verbose mode"
    )
    parser.add_argument(
        "--query", type=str, default="dl=0", help="The query string for generated URLs"
    )
    parser.add_argument(
        "--plus-for-space",
        action="store_true",
        help="Convert URL-encoded spaces to a plus",
    )

    args = parser.parse_args()

    return args


if __name__ == "__main__":
    main()
