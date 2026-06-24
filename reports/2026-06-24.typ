// rQuant Daily Review — 2026-06-24
// Automatically generated. Confidential. Not investment advice.

#set page(
  paper: "a4",
  margin: (top: 2cm, left: 1.8cm, right: 1.8cm, bottom: 1.5cm),
  numbering: "1",
)

#set text(font: ("New Computer Modern", "Noto Serif CJK SC", "Noto Sans CJK SC", "PingFang SC", "Songti SC"), lang: "zh", size: 9.5pt)
#set par(justify: true, leading: 0.55em)

// 标题样式
#show heading.where(level: 1): it => {
  set text(size: 13pt, weight: "bold", fill: rgb("#0f172a"))
  it.body
  v(2pt)
  line(length: 100% - 4pt, stroke: (paint: rgb("#0f172a"), thickness: 1pt))
  v(10pt)
}

= 每日量化复盘 — 2026-06-24

#text(size: 9pt, fill: rgb("#64748b"))[生成时间: 2026-06-24 05:48:30   |   标的池: 7 只   |   信号总数: 18 条]

#v(8pt)



// ---------- Top-5 荐股 ----------

= 明日推荐买入标的 Top-5

#figure(
  table(
  stroke: (x, y) => if y == 0 { (top: 1.5pt + rgb("#0f172a"), bottom: 0.5pt + rgb("#0f172a")) } else if y == 5 { (bottom: 1.5pt + rgb("#0f172a")) },
    inset: (x: 5pt, y: 4pt),
    columns: (auto, auto, 1fr, 1fr, auto),
    align: (center, center, left, left, center),
    table.header(
      [*排名*],
      [*代码*],
      [*名称*],
      [*策略*],
      [*置信度*],
    ),
  [1], [sh600460], [士兰微], [DividendLowvolRotation], [#text(fill: rgb("#16a34a"), weight: "bold")[80.0\%]],
  [2], [sh512480], [sh512480], [MultiFactor], [#text(fill: rgb("#b45309"), weight: "bold")[72.2\%]],
  [3], [sh600519], [贵州茅台], [CrossBorderDca], [#text(fill: rgb("#64748b"), weight: "bold")[57.1\%]],
  [4], [sh510500], [sh510500], [DividendLowvolRotation], [#text(fill: rgb("#64748b"), weight: "bold")[50.7\%]],
  [5], [sh601318], [中国平安], [GridMartingale], [#text(fill: rgb("#64748b"), weight: "bold")[46.2\%]],
  ),
  caption: [按置信度排序的前 5 个买入信号。],
  kind: table,
)

#v(6pt)

= 推荐理由


#v(8pt)
+ #text(fill: rgb("#16a34a"), weight: "bold")[80.0\%] *士兰微* (sh600460)  ——  DividendLowvolRotation
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 47.04 / 买入 47.28 / 止损 42.55 / 止盈 52.95]
  #text(size: 8.5pt, fill: rgb("#334155"))[红利低波轮动：20日动量 +37.58%，量比 1.16，现价 > MA20×0.98（¥35.583）]

+ #text(fill: rgb("#b45309"), weight: "bold")[72.2\%] *sh512480* (sh512480)  ——  MultiFactor
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 2.512 / 买入 2.52 / 止损 2.32 / 止盈 2.9]
  #text(size: 8.5pt, fill: rgb("#334155"))[多因子综合 +0.57（8 因子）| Top3: M2 momentum 60d +0.15 / M1 momentum 20d +0.14 / T1 ma20 bias +0.12]

+ #text(fill: rgb("#64748b"), weight: "bold")[57.1\%] *贵州茅台* (sh600519)  ——  CrossBorderDca
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 1222.45 / 买入 1228.56 / 止损 1130.28 / 止盈 1351.42]
  #text(size: 8.5pt, fill: rgb("#334155"))[跨境定投：现价 ¥1222.450 < MA60×0.95（¥1288.216），RSI=30.7，量比=1.22]

+ #text(fill: rgb("#64748b"), weight: "bold")[50.7\%] *sh510500* (sh510500)  ——  DividendLowvolRotation
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 8.815 / 买入 8.86 / 止损 7.97 / 止盈 9.92]
  #text(size: 8.5pt, fill: rgb("#334155"))[红利低波轮动：20日动量 +0.33%，量比 1.10，现价 > MA20×0.98（¥8.328）]

+ #text(fill: rgb("#64748b"), weight: "bold")[46.2\%] *中国平安* (sh601318)  ——  GridMartingale
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 50.4 / 买入 50.5 / 止损 46.23 / 止盈 54.13]
  #text(size: 8.5pt, fill: rgb("#334155"))[网格买入：现价 ¥50.400 位于 20 日区间 ¥48.660-¥55.960 的 24% 位置]



