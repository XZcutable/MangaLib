This application will read manga on the machine

## Development ##

To setup the dev environment, first create a venv if it's not already:
`python -m venv .venv`

Then activate the venv:
`.\.venv\Scripts\activate` on windows or `. .venv/bin/activate` for linux

Then install Flask and Flask-SQLAlchemy:
`pip install Flask Flask-SQLAlchemy`

Then init the database with:
`flask mangalib init-db`

Finally run the server with a command like:
`flask --app mangalib run --debug --host=0.0.0.0`

Depending on your needs, the command may be different

# Creating the Database #

# Running #
To run, activate venv with `.\.venv\Scripts\activate` on windows or `. .venv/bin/activate` on linux. Then run `flask --app mangalib run --debug --host=0.0.0.0`

