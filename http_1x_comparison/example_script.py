import requests

if __name__ == "__main__":
    for _ in range(10):
        res = requests.get('http://localhost:8080/')
        res_2 = requests.get('http://localhost:8080/static/fake_img.txt')
