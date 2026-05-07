# Skill JSON Schemas (Canonical Examples)

本文件集中維護各 `docs/agents/*.md` 引用的 JSON 範例欄位，欄位命名以目前程式實作為準（`src/*.py`）。

## Macro (`macro_analytics`)

```json
{
  "formation_timeline": [
    {"start": "00:00", "end": "00:30", "type": "circle", "ratio": 0.82},
    {"start": "00:30", "end": "01:00", "type": "scatter", "ratio": 0.65}
  ],
  "heatmap_grid": [
    [0.12, 0.35, 0.08],
    [0.05, 0.18, 0.04],
    [0.22, 0.41, 0.19]
  ],
  "hotspot_zones": ["中中", "下中"],
  "underused_zones": ["上左", "中右"],
  "avg_distance_timeline": [
    {"time": "00:00", "avg_cm": 95.0},
    {"time": "00:05", "avg_cm": 88.0}
  ],
  "overall_avg_cm": 102.0,
  "min_cm": 62.0,
  "max_cm": 187.0,
  "engagement_score": 0.78,
  "engagement_timeline": [
    {"time": "00:00-全片", "rate": 0.78}
  ],
  "low_engagement_periods": [],
  "warnings": [],
  "heatmap_png": "/abs/path/tmp/kinder-heatmap.png"
}
```

## Micro (`micro_analytics`)

```json
{
  "children": [
    {
      "child_id": "1",
      "track_id": 14,
      "bpm": 119.84,
      "avg_error_ms": 48.27,
      "sync_rating": "優秀",
      "stop_signals_detected": [
        {"signal_time": "45.0", "displacement_cm": 3.2}
      ],
      "avg_displacement_cm": 3.2,
      "stability_rating": "優秀",
      "concern_flag": false,
      "avg_jerk": 2.104,
      "fluency_rating": "普通",
      "trajectory_image": "/abs/path/tmp/kinder-child-1-trajectory.png",
      "student_id": "S_NEW_0007",
      "display_name": "孩子 7",
      "identity_source": "reid"
    }
  ],
  "bpm_hint": 119.84,
  "warnings": [],
  "tracking": "bytetrack",
  "vid_stride": 3,
  "pose_backend": "yolo+mediapipe_pose",
  "reid_by_track": {
    "14": {
      "student_id": "S_NEW_0007",
      "display_name": "孩子 7",
      "confidence": 0.9134,
      "status": "returning",
      "source": "arcface_track_mean"
    }
  },
  "ai_warnings": [],
  "ai_section_appended": false
}
```

## Metrics (`metrics_checker`)

```json
{
  "check_timestamp": "2026-05-01 06:40",
  "overall_status": "🟡 良好（綜合分 0.78）",
  "overall_score": 0.78,
  "macro_metrics": {
    "group_engagement": {
      "value": 0.82,
      "status": "🟢 綠燈",
      "interpretation": "群體關鍵點位移活躍比例（代理指標）"
    },
    "formation_stability": {
      "value": 0.68,
      "status": "🟡 黃燈",
      "interpretation": "隊形時間窗內幾何分類信心均值"
    },
    "space_utilization": {
      "value": 0.19,
      "status": "🟡 黃燈",
      "interpretation": "熱區 3×3 分佈離散度（標準差）"
    }
  },
  "micro_metrics": {
    "sync_score": {
      "value_ms": 72.0,
      "status": "🟢 綠燈",
      "interpretation": "個體平均同步誤差"
    },
    "stability_score": {
      "value_cm": 11.3,
      "status": "🟡 黃燈",
      "interpretation": "停止信號後髖部位移（平均）"
    },
    "fluency_score": {
      "value_jerk": 4.2,
      "status": "🟡 黃燈",
      "interpretation": "髖部軌跡 jerk 代理值"
    }
  },
  "concern_children": [
    {
      "child_id": "1",
      "display_label": "孩子 1",
      "reason": "抑制控制 / 穩定度偏低；節奏同步誤差偏高",
      "priority": "high"
    }
  ],
  "recommendations_summary": [
    "依紅黃燈檢視課程節奏與停止信號設計",
    "對關注名單加強一對一視線提示與分段任務"
  ]
}
```

## Identity Midframe Map (`identity`)

```json
{
  "items": [
    {
      "slot": 0,
      "student_id": "S_NEW_0007",
      "display_name": "孩子 7",
      "confidence": 0.9134,
      "status": "returning"
    },
    {
      "slot": 1,
      "student_id": "S_NEW_0012",
      "display_name": "孩子 12",
      "confidence": 0.27,
      "status": "new"
    }
  ]
}
```

## Identity Track ReID (`micro.reid_by_track`)

```json
{
  "14": {
    "student_id": "S_NEW_0007",
    "display_name": "孩子 7",
    "confidence": 0.9134,
    "status": "returning",
    "source": "arcface_track_mean"
  }
}
```

