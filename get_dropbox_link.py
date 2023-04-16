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

import argparse
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path as P

import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import ApiError, AuthError

# This is the App Key, NOT an OAuth2 token. Find your app's key in the App Console.
# See the README.
APP_KEY = ""

# Either 'personal' or 'business'. Must match the account which generated
# the TOKEN above.
# See <https://help.dropbox.com/installs-integrations/desktop/locate-dropbox-folder>
ACCOUNT_TYPE = "personal"

# Path to save script configuration. You probably don't need to change this.
CONFIG_JSON = "~/.get_dropbox_link_conf.json"


def main():
    local_dbx_path = None
    args = parseArguments()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    refresh_token = get_refresh_token()

    with dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=APP_KEY) as dbx:
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

def get_refresh_token():
    # Check if the refresh token file exists and contains a token
    config_path = P(CONFIG_JSON).expanduser()
    refresh_token = None

    try:
        with open(config_path) as f:
            config_path = json.load(f)
            refresh_token = config_path.get("refresh_token")
    except Exception as e:
        pass

    # If the config file doesn't exist or doesn't contain a token, go through the auth flow
    if not refresh_token:
        auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, use_pkce=True, token_access_type='offline')

        authorize_url = auth_flow.start()
        webbrowser.open(authorize_url)
        print("Refresh token not found. Let's generate a new one.")
        print("1. Go to: " + authorize_url)
        print("2. Click \"Allow\" (you might have to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()

        try:
            oauth_result = auth_flow.finish(auth_code)
            refresh_token = oauth_result.refresh_token
            
            with open(config_path, 'w') as outf:
                json.dump({"refresh_token": refresh_token}, outf)
        except Exception as e:
            logging.error(str(e))
            exit(1)

    return refresh_token
 

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
