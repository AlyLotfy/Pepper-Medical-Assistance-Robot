import requests

def check_server(url):
    try:
        response = requests.get(url)
        # Check if the response status code is 200 (OK)
        if response.status_code == 200:
            print(f"Success! The server at {url} is reachable.")
        else:
            print(f"Failed to reach the server. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

# URL of your Flask server
UI_URL = "http://1.1.1.244:8080/"

check_server(UI_URL)
