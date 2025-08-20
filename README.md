# codex的任务说明

> codex自行更新此文件，并记录任务进度和更新时间

### 当前目录结构为

```
.
├── .gitignore
├── README.md
├── requirements.txt
├── download_audio.py
├── client_http.py
├── client_ws.py
├── server.py
└── test_tenvad.py
```

### 环境准备

```bash
pip install -r requirements.txt
```

> 注意: `ten-vad` 依赖 `libc++.so.1`，某些系统需额外安装 `libc++1`

### 使用步骤

1. `python download_audio.py` 下载示例音频 `input.wav`
2. `python server.py` 启动 VAD 服务
3. 另开终端测试:
   - `python client_http.py`
   - `python client_ws.py`
4. 或运行 `python test_tenvad.py` 自动完成全部流程并生成:
   - `results.txt`
   - `speech_http.wav` / `speech_ws.wav`
   - `comparison.png`

### 最新进度

- 新增 `download_audio.py` 和 `requirements.txt`
- `python test_tenvad.py` 会启动 `server.py`，通过 HTTP 和 WebSocket 处理音频并输出对比结果
- **Note**: 若运行时报 `libc++.so.1` 找不到，可尝试安装系统包 `libc++1`
=======
- 测试音频已保存为 `input.wav`
- 运行 `python test_tenvad.py` 会
  - 调起本地 `server.py` 服务
  - 分别通过 HTTP 与 WebSocket 接口处理音频
  - 结果写入 `results.txt`
  - 输出人声音频 `speech_http.wav` 与 `speech_ws.wav`
  - 绘制对比图 `comparison.png`

