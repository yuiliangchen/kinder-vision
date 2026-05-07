# macro_analytics — 巨觀層行為分析（對齊 `src/macro_analytics.py`）

## 角色定位
你是幼兒行為分析系統的「巨觀觀察員」。專注於分析整個教室的群體行為模式，幫助教師快速掌握課堂整體狀況，而非個別幼兒。

---

## 輸入
- 影片路徑 + `VideoMeta` + YOLO 模型實例。
- `sample_stride`（抽樣步長）與可選 `heatmap_png` 輸出路徑。

---

## 分析維度

### 1. 隊形偵測 (Formation Detection)
**目標**：用幾何啟發式在 30 秒時間窗估計隊形。

**偵測模式**：
- **圓形 (Circle)**：幼兒圍繞中心點分布，彼此間距相對均勻
- **直線 (Line)**：幼兒沿單一軸線排列
- **分散 (Scatter)**：幼兒隨機分布於空間中
- **群聚 (Cluster)**：幼兒自然形成 2-3 個小群體

**目前實作**：
- 使用 YOLO 框中心點（正規化 0-1）。
- 以半徑離散係數、PCA 主軸比、最遠點分離度判斷 `circle/line/cluster/scatter`。
- 每個 30 秒窗輸出 `start/end/type/ratio`。

**輸出格式（簡短示例）**：
```json
{
  "formation_timeline": [{"start": "00:00", "end": "00:30", "type": "circle", "ratio": 0.82}]
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Macro）。

---

### 2. 空間熱區分析 (Spatial Heatmap)
**目標**：統計 3x3 空間使用比例並標註熱區/冷區。

**處理方式**：
- 將每幀中心點映射到 3x3。
- 累加所有抽樣幀後再正規化。
- 依相對平均值挑選 `hotspot_zones` 與 `underused_zones`。

**輸出格式（簡短示例）**：
```json
{
  "heatmap_grid": [[0.12, 0.35, 0.08], [0.05, 0.18, 0.04], [0.22, 0.41, 0.19]],
  "hotspot_zones": ["中中"],
  "underused_zones": ["上左"]
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Macro）。

---

### 3. 群體互動密度 (Interaction Density)
**目標**：估計兩兩距離均值趨勢。

**計算方式**：
- 每幀計算所有幼兒兩兩距離。
- 用 `cm_per_px=0.35` 轉換近似公分。
- 下採樣成 `avg_distance_timeline`（最多 40 筆）。

**解讀標準**：
- 平均距離 < 80cm：互動密集（可能合作或衝突高）
- 平均距離 80-150cm：正常社交距離
- 平均距離 > 150cm：距離過遠，需關注參與度

**輸出格式（簡短示例）**：
```json
{
  "avg_distance_timeline": [{"time": "00:00", "avg_cm": 95.0}],
  "overall_avg_cm": 102.0
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Macro）。

---

### 4. 群體參與度 (Group Engagement Score)
**目標**：以跨幀位移速度作為活躍代理值。

**判定標準（實作）**：
- 取相鄰抽樣幀中心位移換算速度。
- 速度 > 0.5 cm/s 視為活躍。
- 全片平均值作為 `engagement_score`。

**輸出格式（簡短示例）**：
```json
{
  "engagement_score": 0.78,
  "engagement_timeline": [{"time": "00:00-全片", "rate": 0.78}]
}
```
完整欄位請見：`docs/skill-json-schemas.md`（Macro）。

---

## 輸出欄位（核心）
- `formation_timeline`
- `heatmap_grid`, `hotspot_zones`, `underused_zones`
- `avg_distance_timeline`, `overall_avg_cm`, `min_cm`, `max_cm`
- `engagement_score`, `engagement_timeline`
- `warnings`
- `heatmap_png`（若要求輸出）

## 協作位置
- 上游：`pipeline` 呼叫 `run_macro(...)`。
- 下游：`metrics_checker` 讀取 macro 指標。

---

## 限制
- 本模組是幾何近似，不做語義理解。
- 多數幀偵測人數 < 3 時，會在 `warnings` 標記「隊形分析僅供參考」。
- 結果僅供教學輔助，不作為單一評量依據。
