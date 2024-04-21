# WebRecorder
A FastAPI + Playwright Web Backend that can record the page of a website from it's URL


## Requirements
- Docker v4.23.0 and above (optional, check out [Running without Docker](#running-without-docker))


## Setup Guide
- Clone the repository

    ```bash
    git clone https://github.com/AkshuAgarwal/WebRecorder
    cd WebRecorder
    ```

- Make sure you have [Docker](https://docker.com) installed. If not, install and set it up.

- Setup the environment variables
    - Rename [`.env.prod.example`](./.env.prod.example) to `.env.prod`

    - Set the values to the environment variables in the file
        - `ENVIRONMENT`: The current working environment (`development`/`production`). Do not change it as it is already synced with the env file.

        - `REDIS_URL`: URL of the redis server to connect to.

- Run the code using docker compose

    ```bash
    # For production environment
    docker compose -f docker-compose.yaml -f docker.compose.prod.yaml up
    ```


## Running without Docker

If you wish to run the server without using docker, you can follow the instructions below to set up everything manually.

## Requirements (without Docker)

- Python 3.11 and above
- Redis Stack Server 7.2.4 and above


## Setup Guide (without Docker)
- Clone the repository

    ```bash
    git clone https://github.com/AkshuAgarwal/WebRecorder
    cd WebRecorder
    ```

- Install and setup [Redis Stack Server](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/)

- Install the required python packages
    - Create and activate the virtual environment (optional)

        ```bash
        python -m venv .venv
        
        # Linux
        source .venv/bin/activate

        # Windows
        .venv/Scripts/activate
        ```
    
    - Install the packages

        ```bash
        python -m pip install -r requirements.txt
        ```

    - Install playwright

        ```bash
        playwright install chromium
        playwright install-deps
        ```

- Setup the environment variables
    - Rename [`.env.example`](./.env.example) to `.env`

    - Set the values to the environment variables in the file
        - `REDIS_URL`: URL of the redis server to connect to.

- Run the Redis Server

    ```bash
    redis-stack-server
    ```

- Start the application

    ```bash
    python server run

    # For all the commands, run `python server help`
    ```

> If you want to use Nginx, you can do it manually by following their documentation and configure the server accordingly.


## Limitations

- The server can only run on one worker/process. Playwright does not support using multiple workers or processes and will result in an error.

- Video recording is slow. The server runs a chromium instance, opens the website, scrolls down through the webpage and simultaneously records it all. The recording takes some time, dependingg on the scroll speed (which is set to 300 pixels/sec by default).

- The server requires read and write access to filesystem since it saves and reads the recorded video from the source filesystem and not in/from IO Buffers.

- The recording process is blocking. That means when a request comes while other video is still recording, the server will push it to a queue and will not start recording until all the previous recordings gets completed.
