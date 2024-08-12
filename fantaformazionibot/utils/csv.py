import requests


def download_csv(url: str, dest_path: str) -> None:
    response = requests.get(url)
    with open(dest_path, "wb") as file:
        file.write(response.content)