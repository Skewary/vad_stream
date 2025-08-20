#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
from tqdm import tqdm

def download_file(url: str, local_filename: str):
    """下载文件并保存到本地"""
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(local_filename, "wb") as f, tqdm(
        desc=local_filename,
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))
    return local_filename


if __name__ == "__main__":
    # Sherpa-ONNX Release 地址（腾讯 ten-vad ONNX 模型）
    url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.9.1/ten-vad.onnx"
    local_path = "ten-vad.onnx"

    if not os.path.exists(local_path):
        print(f"正在下载 {url} -> {local_path}")
        download_file(url, local_path)
    else:
        print(f"{local_path} 已存在，跳过下载")
