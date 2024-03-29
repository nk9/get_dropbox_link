#!/usr/bin/python3
# coding=utf-8

# Copyright 2023 Nick Kocharhook
# MIT Licensed

# https://github.com/nk9/get_dropbox_link

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
from urllib.parse import urlparse, parse_qs, urlencode

import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.sharing import PendingUploadMode


class AccountType(IntEnum):
    PERSONAL = 1
    BUSINESS = 2


# ADVANCED SETTINGS (Leave these alone.)
# Path to save script configuration.
CONFIG_PATH = "~/.get_dropbox_link_conf.json"

# Number of concurrent requests to the Dropbox API.
MAX_WORKERS = 10

VERSION = 4


def main():
    args = parseArguments()

    if args.version:
        print(f"{VERSION}")
        sys.exit(0)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    config_path = Path(CONFIG_PATH).expanduser()
    fetcher = LinkFetcher(config_path, args.query, args.plus_for_space)
    fetcher.fetch(args.paths)


class LinkFetcher:
    def __init__(self, config_path, query, plus_for_space):
        self.config = Config.with_path(config_path)
        self.config.require_app_key()

        self.query = self.parse_query(query)
        self.plus_for_space = plus_for_space

    def fetch(self, paths):
        local_dbx_path = None
        refresh_token = self.get_refresh_token()

        with dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            oauth2_access_token=self.config.access_token,
            oauth2_access_token_expiration=self.config.access_token_expiration,
            app_key=self.config.app_key,
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
                    local_dbx_path = info[self.config.account_type.name.lower()]["path"]
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
            link = dbx.sharing_create_shared_link(
                dbx_path, pending_upload=PendingUploadMode.file
            )
            logging.debug(f"Shared link returned: {link}")
            url = urlparse(link.url)

            if self.query:
                merged = {**parse_qs(url.query), **self.query}

                # Remove any empty items
                query_dict = {k: v for k, v in merged.items() if v != [""]}
                new_query_string = urlencode(query_dict, doseq=True)
                url = url._replace(query=new_query_string)

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
                self.config.app_key, use_pkce=True, token_access_type="offline"
            )

            authorize_url = auth_flow.start()
            webbrowser.open(authorize_url)
            print("\n=>Refresh token not found. Let's generate a new one.")
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

    def parse_query(self, qstr):
        query_dict = {}

        if qstr:
            try:
                query_dict = parse_qs(qstr, strict_parsing=True, keep_blank_values=True)
            except Exception as e:
                logging.error("Failed parsing provided query: ", str(e))
                sys.exit(1)

        return query_dict


@dataclass
class Config:
    path: Path
    app_key: t.Optional[str]
    account_type: t.Optional[AccountType]
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

    def require_app_key(self):
        save = False

        if self.app_key is None:
            while self.app_key is None or len(self.app_key) < 10:
                print(
                    "=>Please provide your app's App Key. This is NOT an OAuth2 token.\n"
                    "Find the App Key in the App Console. See the README."
                )
                self.app_key = input("App Key: ").strip()

            save = True

        if self.account_type is None:
            account_type_str = ""
            while account_type_str not in {"p", "personal", "b", "business"}:
                print(
                    "\n=> Which kind of Dropbox account is this App Key associated with?"
                )
                account_type_str = input("[p]ersonal or [b]usiness? ").strip().lower()

            if account_type_str in {"p", "personal"}:
                self.account_type = AccountType.PERSONAL
            else:
                self.account_type = AccountType.BUSINESS

            save = True

        # Only save if both values are present and either was modified
        if save:
            self.save()

    def save(self):
        with open(self.path, "w") as config_f:
            json.dump(
                {
                    "app_key": self.app_key,
                    "refresh_token": self.refresh_token,
                    "account_type": self.account_type.name,
                    "access_token": self.access_token,
                    "access_token_expiration": self.access_token_expiration.isoformat(),
                },
                config_f,
            )

    @classmethod
    def from_dict(cls: t.Type["Config"], path: Path, obj: dict):
        expiration = dt.now()
        account_type = None

        if expiration_str := obj.get("access_token_expiration"):
            expiration = dt.fromisoformat(expiration_str)

        if account_type_str := obj.get("account_type"):
            account_type = AccountType[account_type_str]

        return cls(
            path=path,
            app_key=obj.get("app_key"),
            account_type=account_type,
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
            return Config(path, None, None, None, None)


def parseArguments():
    parser = argparse.ArgumentParser(description="Fetch Dropbox URL for path")
    parser.add_argument("paths", type=str, nargs="+", help="paths to files")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="toggle verbose mode"
    )
    parser.add_argument("--version", "-V", action="store_true")
    parser.add_argument(
        "--query", type=str, help="Override query string for generated URLs"
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
