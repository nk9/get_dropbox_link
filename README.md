# Get Dropbox Link
Dropbox should provide a keyboard command to quickly get a link in Finder for a file in the Dropbox folder. Sadly, despite years of requests, this still isn't possible.

So I wrote this script to do that. Read more about it on the [Dropbox Forum](https://www.dropboxforum.com/t5/View-download-and-export/Key-Command-Shortcut-to-quot-Copy-Dropbox-Link-quot-from-Mac/td-p/168482/highlight/false).

The script uses threads to send up to 10 link requests at a time, so it should be quite speedy, especially if you can batch your requests.

## Usage
```
$ get_dropbox_link.py ~/Dropbox/file*
https://www.dropbox.com/s/xxxx/file%20to%20share.txt?dl=0
https://www.dropbox.com/s/xxxx/file2.jpg?dl=0
```

There are a couple of arguments available to change the returned URLs, which can be used independently:
```
$ get_dropbox_link.py ~/Dropbox/file* --plus-for-space --query raw=1
https://www.dropbox.com/s/xxxx/file+to+share.txt?raw=1
https://www.dropbox.com/s/xxxx/file2.jpg?raw=1
```

## Script Setup
1. [Clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) or [download](https://github.com/nk9/get_dropbox_link/archive/refs/heads/main.tar.gz) this git repository.

2. Place the `get_dropbox_link.py` script somewhere in your `PATH`. The rest of these instructions assume you've placed it in `$HOME/bin`.
3. Set the script's permissions so you can run it:

    ```
    chmod +x ~/bin/get_dropbox_link.py
    ```

4. Install the dropbox Python SDK. You may also need to pin urllib3 to an earlier version. (See issue [#6](https://github.com/nk9/get_dropbox_link/issues/6) for more.)

    ```
    /usr/bin/python3 -m pip install dropbox
    /usr/bin/python3 -m pip install urllib3==1.26.6
    ```

5. [Create a Dropbox app](https://blogs.dropbox.com/developers/2014/05/generate-an-access-token-for-your-own-account) on the [Dropbox App Console](https://www.dropbox.com/developers/apps).
6. Give the app an access type of Full Access.
7. Create it.
8. Change the Permissions settings to have a scope of `sharing.write`.

![Change sharing.write permission setting](assets/sharing.write.jpg)

9. Copy the App Key:

![Copy App Key on the Settings tab](assets/app-key.jpg)

10. Use this to update the `APP_KEY` variable on line 51 in the script file.
11. If you use a Dropbox Business account, change the `ACCOUNT_TYPE` variable on line 54.

12. Call the script once and follow the instructions to get a refresh token the first time:

    ```
    $ get_dropbox_link.py ~/Dropbox/Public/cat.jpg
    Refresh token not found. Let's generate a new one.
    1. Go to: https://www.dropbox.com/oauth2/authorize?xxxx
    2. Click "Allow", etc. (You may need to log in first.)
    3. Copy the Access Code.
    Enter the Access Code here: xxxx
    https://www.dropbox.com/s/xxxx/cat.jpg?dl=0
    ```
    Now you can continue calling it to generate links.

    ```
    $ get_dropbox_link.py ~/Dropbox/file.txt ~/Dropbox/file2.txt
    https://www.dropbox.com/s/xxxx/file.txt?dl=0
    https://www.dropbox.com/s/xxxx/file2.txt?dl=0
    $
    ```

## Automator Setup
My goal was to have a keyboard shortcut in Finder that would copy a Dropbox link to the clipboard. If you want to do that too, you'll need to add an [Automator](https://support.apple.com/en-gb/guide/automator/welcome/mac) Quick Action. Choose one of these options:

### Easy Way
1. In your local copy of this repo, double-click the "Get Dropbox Link" workflow.
2. Press Install.
3. There's no step 3.

    > **Warning**
    >
    > If you have installed the script somewhere other than `~/bin/get_dropbox_link.py`, you will need to edit the workflow to point at your custom location. You can find it in ~/Library/Services.

### Manual Way
1. Open Automator and create a new Quick Action.
2. Find and drag over two actions: Run Shell Script, and Copy to Clipboard.
3. In the Run Shell Script action, give it the content of:
    ```
    $HOME/bin/get_dropbox_link.py "$@"
    ```
    > **Warning**
    >
    > Make sure you set the workflow to receive the current files or folders from Finder. Also, change the popup button to _Pass input as arguments_.

    > **Warning**
    >
    > Make sure the path here is the same as the path that you saved the script to earlier!

4. Save the Quick Action to the default location (~/Library/Services). Give it the name you want it to have in the menu, like "Get Dropbox Link".

5. Once you're done, the action should look like this:

    ![Completed Quick Action](assets/quick-action.jpg)

> **Note**
>
> Please note that pressing "Run" within Automator will complain about missing the `paths` argument. This is correct, and happens because Automator doesn't have any selected Finder items to pass into the workflow. Instead, you need to hook up the shortcut below and use the workflow as a Quick Action from Finder via the Services menu. Learn more at [AskDifferent](https://apple.stackexchange.com/questions/379096/why-automators-component-get-selected-finder-items-duplicates-path-of-selecte/379100#379100) and [Apple Support](https://support.apple.com/en-gb/guide/automator/aut73234890a/mac).


## Finder Shortcut
Now that you have the script and workflow installed, the last piece is the Finder shortcut.

1. Open System Preferences > Keyboard > Shortcuts and navigate to Services. In the outline view, under "Files and Folders", locate the "Get Dropbox Link" service.
2. Make sure the checkbox to the left is checked, and give it a shortcut. Here, I've  chosen <kbd>Cmd</kbd>+<kbd>Ctrl</kbd>+<kbd>L</kbd>.

![Assigning the keyboard shortcut](assets/keyboard-shortcut.jpg)

3. Now, you can test it! Go to your Dropbox folder in Finder. Select at least one file and press <kbd>Cmd</kbd>+<kbd>Ctrl</kbd>+<kbd>L</kbd>. Your clipboard should now contain the links to the files. Note that when creating multiple links, each link has to be requested individually, so there may be a delay before the links appear on your clipboard. Watch for the spinning Automator gear in your menu bar.
