# media / 本地影音素材

文件與 API 範例多以 **`media/demo.mp4`** 為慣例路徑；`video_path` 仍可為任意相對／絕對路徑。

## `demo.mp4`

請自行將欲分析的 `.mp4`（或 `.mov`／`.avi`）複製為：

```
media/demo.mp4
```

此類影音檔因 `.gitignore`（`*.mp4`、`*.MOV`）**不會**進入版控。

若要自行生一支最小測試片（需已安裝 `ffmpeg`）：

```bash
ffmpeg -y -f lavfi -i testsrc=duration=5:size=640x360:rate=10 -f lavfi -i sine=frequency=440 -pix_fmt yuv420p -shortest media/demo.mp4
```
