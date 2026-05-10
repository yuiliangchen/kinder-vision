# identity — 身分管理與 ReID 歸戶（對齊 `src/identity.py`、`src/pipeline.py`、`src/micro_analytics.py`）

## 角色定位
你是幼兒分析系統的「記憶中樞」。負責將 YOLO 偵測到的臨時編號（如 Person_01）與資料庫中的特定幼兒身分（如 Student_007 小明）進行精準綁定，並提供跨時段的追蹤依據。

---

## 核心功能（目前實作）

### 1. 身分資料庫載入與比對
- identity db 位於 `memory/identity_features.db.json`。
- `assign_identity` 以 cosine similarity 比對 `features.face_embedding_sample`。
- 主閾值（中間幀與 ArcFace 軌跡均值）：`0.85`。
- 若低於閾值，`assign_identity` 回傳暫時 `S_NEW_####`（狀態 `new`）；上層 `micro_analytics` 會再為每條軌跡補上獨立後綴（見「3. 兩段式歸戶」）以確保不同 track 不會塌成同一個編號。

### 2. 外觀 embedding fallback
- `appearance_embedding_from_patch` 使用 HSV histogram（預設 128 維）。
- 微觀軌跡 ReID 中，若 ArcFace 不可得，改用外觀均值向量比對，閾值 `0.72`。


### 3. 兩段式歸戶
- **中間幀槽位映射**：`pipeline._identity_pass` 先建立 slot -> student_id。
- **整片軌跡 ReID**：`micro.reid_by_track` 以 track 均值向量歸戶。
- 合併策略：優先 `reid_by_track`，失敗再回退中間幀槽位。

#### 軌跡層唯一性保證（micro_analytics）
當同一場跑出多條 track 但 identity db 為空（典型情況：未啟用 `--learn-identities`）時，`assign_identity` 會把每條 track 都當成「第 1 個新身分」回傳 `S_NEW_0001`。為避免結果塌成同一個「孩子 1」，`micro_analytics` 會：

1. **依 track id 排序**（數字優先，字串 fallback）後依序處理，確保每次跑的編號穩定。
2. **替每條新軌跡產生獨立的 `student_id`**：把回傳的 `S_NEW_####` 加上軌跡後綴，例如 `S_NEW_0001_T8`、`S_NEW_0001_T15`，並依出現順序配發 `孩子 1`、`孩子 2`、`孩子 3`…
3. **完全沒有 embedding 的 track**：以 `T_<tid>` 當 `student_id`、source 標記為 `track_fallback`，仍會配獨立編號。
4. **多條 track 命中同一個既有身分（returning）**：保留主編號，但 `display_name` 加上「（軌跡 N）」後綴，避免下游報告把不同軌跡的指標合併。

下游（`metrics_checker` / `edu_advisor`）優先採用 `display_name` 而非反向重算，避免同樣的塌縮再次發生。

#### 軌跡合併與成人過濾（within-run ReID）
ByteTrack 在遮蔽、交叉、走出畫面時常重發新的 track id，25 秒的班級影片有時會跨出 50+ 條 track。`micro_analytics` 在計算個人指標之前會以 face / appearance embedding 進行 **within-run ReID**：

1. **長度過濾**：少於 8 幀的軌跡不參與 clustering（幽靈 track），但仍以獨立身分保留。
2. **時間不重疊硬限制**：任何在同一時間窗口內重疊超過 0.25s 的 track 不能合併，避免同畫面中的兩人被誤併。
3. **敢心合併 (greedy by similarity)**：取全部非重疊 pair 的 face cosine similarity，由高到低排序，依序嘗試合併；appearance embedding 以較高閾值作為輔助證據。
4. **Cluster-level overlap check**：每次合併前检查所有跨 cluster 的成員是否有重疊，避免 transitive 收斂掛入同畫面出現的人。

閾值以 buffalo_l 在教室遠拍影片的實測分佈設定（face 默認 0.62，app 0.88），可在區區 25 秒內將 ≈3× 軌跡量收斂為實際身分。

##### 成人過濾
classroom 內常出現老師與他人員，需在報告中排除。目前採三層策略：

- **主要 (`_classify_adult_tracks_by_height`)**：以 cluster 的 bbox 高度中位數對比班級中位，超過 1.35× 視為成人。
- **備援 (`_classify_adult_tracks` via face age)**：當高度訊號不足時改用 buffalo_l face age（中位數 ≥ 18）。**重要：buffalo_l 的 face age 在低解析 / 小臉場景上不可靠**（完整實測顯示所有人腦被估為 25–35），故只當高度證據完全缺失時才使用。
- **`reid_by_track` 與 `cluster_summary`**：輸出仍以「身分 (cluster root)」為單位。`cluster_summary` 包含 `raw_tracks` / `merged_identities` / `adults_excluded` / `children_kept`，供下游追蹤收斂成效。

---

## 命名與顯示規則
- `display_label_for_student_id("S_NEW_0007")` -> `孩子 7`（僅辨識純 `S_NEW_####` 形態）。
- 帶軌跡後綴的編號（如 `S_NEW_0001_T8`、`T_42`）不走反向解析，請直接使用上游已備好的 `display_name`。
- 「孩子 N」的 N 來自「軌跡合併後依畫面中心 (cx) 由左到右排序」的序號，與 `student_id` / cluster root 無關。同一人在同一場跑中 N 是唯一的。
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
