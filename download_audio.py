import requests

AUDIO_URL = "https://paddlespeech.bj.bcebos.com/PaddleAudio/zh.wav"
OUTPUT = "input.wav"


def main():
    resp = requests.get(AUDIO_URL)
    resp.raise_for_status()
    with open(OUTPUT, "wb") as f:
        f.write(resp.content)
    print(f"已下载示例音频到 {OUTPUT}")


if __name__ == "__main__":
    main()
