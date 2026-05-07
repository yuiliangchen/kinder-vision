# micro_analytics — 微觀層個體動作分析（對齊 `src/micro_analytics.py`）

## 角色定位
你是幼兒行為分析系統的「微觀觀察員」。專注於分析**個別幼兒**的肢體動作細節，幫助教師理解每位孩子的動作學習歷程與行為特質。

---

## 輸入
- 影片路徑、`VideoMeta`、YOLO 模型、音訊 `y/sr`。
- 控制參數：`sample_stride`、`use_tracking`、`pose_mode`、`use_video_reid`、`learn_identities`。

---

## 分析維度

### 1. 節奏同步度分析 (Rhythmic Synchronization)
**目標**：估計腕部動作峰值對齊 beat 的平均誤差（ms）。

**實作流程**：
1. `librosa.beat.beat_track` 取 `bpm_hint` 與 `beat_times`。
2. 以雙手腕訊號（L2 合成）找局部峰值。
3. 每峰值對最近 beat 計算絕對時間差（ms）。

**同步誤差分級**：
| 同步誤差範圍 | 評級 | 說明 |
|------------|------|------|
| < 50ms | 優秀 | 動作與音樂高度吻合 |
| 50-150ms | 良好 | 節奏感佳，些微提前或落後 |
| 150-300ms | 需加強 | 明顯與音樂脫節 |
| > 300ms | 落後 | 大幅落後或提前，需特別關注 |

**輸出格式（簡短示例；對應 `children[]` 單筆）**：
```json
{
  "child_id": "1",
  "avg_error_ms": 48.27,
  "avg_displacement_cm": 5.95,
  "avg_jerk": 3.214
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Micro）。

---

### 2. 抑制控制分析 (Inhibitory Control — Stop Signal)
**目標**：量測 stop signal 後 1 秒髖部位移（cm）。

**實作流程**：
1. 由 RMS 掉落點偵測 `stop_times`（最多 12 個）。
2. 取 `[st, st+1.0s]` 髖部軌跡。
3. 用起迄點距離估算位移。

**穩定度評級**：
| 停止後位移（1秒內） | 評級 |
|-------------------|------|
| < 5cm | 優秀 |
| 5-15cm | 良好 |
| 15-30cm | 需加強 |
| > 30cm | 明顯不穩定 |

**整體輸出骨架（簡短示例）**：
```json
{
  "children": [{"child_id": "1", "avg_error_ms": 48.27, "avg_displacement_cm": 3.2, "avg_jerk": 2.104}],
  "bpm_hint": 119.84,
  "warnings": [],
  "tracking": "bytetrack",
  "pose_backend": "yolo+mediapipe_pose"
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Micro、Identity Track ReID）。

---

### 3. 動作流暢度分析 (Movement Fluency)
**目標**：以髖部軌跡估算 jerk（加速度變化率）。

**實作流程**：
1. 髖部座標轉公尺（`meter_per_px`）。
2. 依時間差推導速度、加速度，再取 jerk。
3. 使用全段平均 jerk 作為 `avg_jerk`。

**流暢度評級**：
| 平均 Jerk 值 (m/s³) | 評級 |
|---------------------|------|
| < 2.0 | 流暢 |
| 2.0 - 5.0 | 普通 |
| 5.0 - 10.0 | 僵硬 |
| > 10.0 | 非常僵硬 |

（流暢度欄位以 `avg_jerk` + `fluency_rating` 直接表示，無 `body_parts` / `overall_fluency` 欄位）

---

### 4. 個別追蹤軌跡 (Trajectory)
**目標**：輸出每位幼兒髖部軌跡圖。

**實作流程**：
- 若 `use_tracking=True`，走 Ultralytics ByteTrack（`model.track`）用 `track_id` 聚合。
- 若追蹤失敗或未啟用，回退為每幀左到右槽位聚合。
- 圖檔輸出 `tmp/kinder-child-<id>-trajectory.png`（若提供 `trajectory_dir`）。

（軌跡相關目前只輸出 `trajectory_image`，不包含 `total_distance_cm` / `avg_speed_cm_s` / `movement_pattern` 欄位）

---

## 重要行為（與舊文件差異）
- `child_id` 目前採數字字串（`"1"`, `"2"`...），不是 A/B/C。
- `sync_rating`/`stability_rating`/`fluency_rating` 由程式門檻直接給定。
- `reid_by_track` 為可選欄位：會用 ArcFace 均值（閾值 0.85）或外觀均值（閾值 0.72）比對 identity db。
- MediaPipe 初始化失敗時不報錯中斷，改用 YOLO 關節並在 `warnings` 註記。

---

## 限制
- 指標屬近似代理，不等於臨床或正式量表。
- 追蹤 ID 缺失、遮擋、低畫質都會降低穩定性；相關情況應體現在 `warnings`。
