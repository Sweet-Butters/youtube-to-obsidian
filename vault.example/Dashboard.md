---
tags: [dashboard]
---

# YouTube Notes Dashboard

> Requires the Dataview community plugin (`Settings → Community plugins → Dataview`).

## Recently watched / 최근 본 영상

```dataview
TABLE
  channel AS "Channel",
  category AS "Category",
  date_watched AS "Watched",
  duration AS "Duration"
FROM "YouTube"
SORT date_watched DESC
LIMIT 30
```

## By category / 카테고리별 모아보기

```dataview
TABLE WITHOUT ID
  file.link AS Note,
  channel AS Channel,
  date_watched AS Watched
FROM "YouTube"
GROUP BY category
SORT category ASC, date_watched DESC
```

## By channel / 채널별 통계

```dataview
TABLE WITHOUT ID
  channel AS Channel,
  length(rows.file.link) AS Count,
  min(rows.date_watched) AS "First watched",
  max(rows.date_watched) AS "Last watched"
FROM "YouTube"
GROUP BY channel
SORT length(rows.file.link) DESC
```

## Tag cloud / 태그 클라우드

```dataview
TABLE WITHOUT ID
  tag AS Tag,
  length(rows) AS Count
FROM "YouTube"
FLATTEN file.tags AS tag
WHERE tag != "#youtube"
GROUP BY tag
SORT length(rows) DESC
LIMIT 30
```
