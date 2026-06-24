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

#text(size: 9pt, fill: rgb("#64748b"))[生成时间: 2026-06-24 10:31:17   |   标的池: 7 只   |   信号总数: 15 条]

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
  [1], [sh512480], [sh512480], [DividendLowvolRotation], [#text(fill: rgb("#b45309"), weight: "bold")[78.5\%]],
  [2], [sh600460], [士兰微], [MultiFactor], [#text(fill: rgb("#b45309"), weight: "bold")[73.7\%]],
  [3], [sh600519], [贵州茅台], [GridMartingale], [#text(fill: rgb("#b45309"), weight: "bold")[67.8\%]],
  [4], [sh601318], [中国平安], [GridMartingale], [#text(fill: rgb("#b45309"), weight: "bold")[63.7\%]],
  [5], [sz000001], [平安银行], [GridMartingale], [#text(fill: rgb("#b45309"), weight: "bold")[60.7\%]],
  ),
  caption: [按置信度排序的前 5 个买入信号。],
  kind: table,
)

#v(6pt)

= 推荐理由


#v(8pt)
+ #text(fill: rgb("#b45309"), weight: "bold")[78.5\%] *sh512480* (sh512480)  ——  DividendLowvolRotation
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 2.652 / 买入 2.67 / 止损 2.4 / 止盈 2.99]
  #text(size: 8.5pt, fill: rgb("#334155"))[红利低波轮动：20日动量 +14.26%，量比 1.18，现价 > MA20×0.98（¥2.195）]

+ #text(fill: rgb("#b45309"), weight: "bold")[73.7\%] *士兰微* (sh600460)  ——  MultiFactor
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 50.01 / 买入 50.26 / 止损 46.24 / 止盈 57.8]
  #text(size: 8.5pt, fill: rgb("#334155"))[多因子综合 +0.62（8 因子）| Top3: M1 momentum 20d +0.20 / M2 momentum 60d +0.15 / T1 ma20 bias +0.12]

+ #text(fill: rgb("#b45309"), weight: "bold")[67.8\%] *贵州茅台* (sh600519)  ——  GridMartingale
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 1207.68 / 买入 1210.1 / 止损 1144.75 / 止盈 1298.0]
  #text(size: 8.5pt, fill: rgb("#334155"))[网格买入：现价 ¥1207.680 位于 20 日区间 ¥1205.000-¥1329.000 的 2% 位置]

+ #text(fill: rgb("#b45309"), weight: "bold")[63.7\%] *中国平安* (sh601318)  ——  GridMartingale
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 49.12 / 买入 49.22 / 止损 46.23 / 止盈 54.13]
  #text(size: 8.5pt, fill: rgb("#334155"))[网格买入：现价 ¥49.120 位于 20 日区间 ¥48.660-¥55.960 的 6% 位置]

+ #text(fill: rgb("#b45309"), weight: "bold")[60.7\%] *平安银行* (sz000001)  ——  GridMartingale
  #text(size: 8.5pt, fill: rgb("#475569"))[现价 10.51 / 买入 10.53 / 止损 9.9 / 止盈 11.15]
  #text(size: 8.5pt, fill: rgb("#334155"))[网格买入：现价 ¥10.510 位于 20 日区间 ¥10.420-¥11.390 的 9% 位置]



