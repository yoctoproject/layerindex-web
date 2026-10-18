VSCode + DevContainers Setup
----------------------------

If you already use VSCode and Docker, you can setup the local development
environment using preconfigured DevContainers extension.

Getting Started
---------------

1. Install Dev Containers extension (ms-vscode-remote.remote-containers)
2. Open local clone of this repository in VSCode
3. Click on "Reopen in Container" when prompted by VSCode
4. Wait 1-2 minutes for VSCode to setup your DevContainer

Once the DevContainer setup process is completed, you'll have access to:

* Django development server running at http://localhost:8000
* All Django database migrations applied
* PyTest autodiscovery and debugger configured
* Database client extension configured with the local server
* Code linting and formatting with ruff
* Command line git support with your SSH keys mounted in the container

FAQ
---

1.  How do I import master branch from the public instance?

    Run the following command in the VSCode Terminal:

    $ layerindex/tools/import_layers.py https://layers.openembedded.org


2.  How do I see emails sent by the development system?

    Emails are logged to the standard output of the layerindex-web container.

    To see the logs:

    1. Open the Command Palette: Ctrl+Shift+P / Cmd+Shift+P
    2. Type: "Remote Explorer: Focus on Dev Containers View"
    3. Right-click on the layerindex-web container
    4. Select "Show Container Log"


3.  How do I interact with Django's manage.py script?

    Open a new terminal window in VSCode and type:

    $ ./manage.py ...