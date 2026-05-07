# identity — 身分管理與 ReID 歸戶（對齊 `src/identity.py`、`src/pipeline.py`、`src/micro_analytics.py`）

## 角色定位
你是幼兒分析系統的「記憶中樞」。負責將 YOLO 偵測到的臨時編號（如 Person_01）與資料庫中的特定幼兒身分（如 Student_007 小明）進行精準綁定，並提供跨時段的追蹤依據。

---

## 核心功能（目前實作）

### 1. 身分資料庫載入與比對
- identity db 位於 `memory/identity_features.db.json`。
- `assign_identity` 以 cosine similarity 比對 `features.face_embedding_sample`。
- 主閾值（中間幀與 ArcFace 軌跡均值）：`0.85`。
- 若低於閾值，回傳新身分 `S_NEW_####`（狀態 `new`）。

### 2. 外觀 embedding fallback
- `appearance_embedding_from_patch` 使用 HSV histogram（預設 128 維）。
- 微觀軌跡 ReID 中，若 ArcFace 不可得，改用外觀均值向量比對，閾值 `0.72`。


### 3. 兩段式歸戶
- **中間幀槽位映射**：`pipeline._identity_pass` 先建立 slot -> student_id。
- **整片軌跡 ReID**：`micro.reid_by_track` 以 track 均值向量歸戶。
- 合併策略：優先 `reid_by_track`，失敗再回退中間幀槽位。

---

## 命名與顯示規則
- `display_label_for_student_id("S_NEW_0007")` -> `孩子 7`。
- 對外一律優先顯示「孩子 N」，避免暴露真名。

---

## 輸出格式 (JSON)

```json
{
  "items": [{"slot": 0, "student_id": "S_NEW_0007", "display_name": "孩子 7", "confidence": 0.9134, "status": "returning"}]
}
```

上例對應 `tmp/kinder-identity-map.json`（中間幀槽位映射）。  
若看整片軌跡 ReID，欄位在 `micro.reid_by_track`，格式如下：

```json
{
  "14": {"student_id": "S_NEW_0007", "display_name": "孩子 7", "confidence": 0.9134, "status": "returning", "source": "arcface_track_mean"}
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Identity Midframe Map、Identity Track ReID）。

---

## 隱私守則 (Privacy Protocol)
1. 去識別化：對外只顯示代號（孩子 N）。
2. 原圖不入庫：identity db 僅儲存向量，不儲存人臉圖片。
3. 功能分離：macro 不依賴身分向量，僅處理群體幾何資訊。

---

## 與其他模組的協作
- 上游：`pipeline` 在中間幀與整片追蹤中觸發歸戶。
- 下游：`micro` / `metrics` / `edu` 使用 `student_id` 與顯示代號。
