import requests

url = "http://localhost:8002/vad"
files = {'file': open("input.wav", "rb")}
resp = requests.post(url, files=files)

if resp.status_code == 200:
    with open("speech_only.wav", "wb") as f:
        f.write(resp.content)
    print("✅ 人声部分已保存到 speech_only.wav")
else:
    print("❌ 未检测到人声")
