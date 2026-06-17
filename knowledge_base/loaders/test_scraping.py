import requests

url = "http://www.phct.com.tn/"
response = requests.get(
    url,
    headers={"User-Agent": "Mozilla/5.0"}
)

print(response.status_code)
print(response.text[:1000])