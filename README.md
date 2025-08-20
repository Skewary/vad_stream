# codex的任务说明

> codex自行更新此文件，并记录任务进度和更新时间

### 当前目录结构为

```
.
├── .gitignore
├──README.md
├──client_http.py
├──client_ws.py
├──server.py
└──test_tenvad.py
```

### 任务进度

- [x] 创建一个基于TEN vad的流式服务端接口。
- [x] 创建一个基于TEN vad的流式客户端
- [x] 创建一个基于TEN vad的非流式接口。
- [x] 下载一个测试音频。
- [x] 用测试音频测试两种接口的效果，并将结果记录文件。
- [x] 用matlabplot绘制流式接口和非流式的人声捕获对比效果。

### 最新进度

- 测试音频已保存为 `input.wav`
- 运行 `python test_tenvad.py` 会
  - 调起本地 `server.py` 服务
  - 分别通过 HTTP 与 WebSocket 接口处理音频
  - 结果写入 `results.txt`
  - 输出人声音频 `speech_http.wav` 与 `speech_ws.wav`
  - 绘制对比图 `comparison.png`



