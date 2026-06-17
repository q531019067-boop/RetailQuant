# Mermaid 踩坑教训

1. **`[\s\S]*?` 匹配跨行内容** — `[^']*` 不匹配 `\n`，跨行的 `"'...\n...'"` 会被漏掉
2. **`\r\n` 行尾** — Windows 文件用 `\r\n`，Python 正则要用 `\r?\n`
3. **`]``` 紧贴** — 关闭符 ` ``` ` 必须独占一行，不能紧贴 `]` 或 `}`
4. **mmdc 需要 `flowchart TD` 头** — 提取内容写入临时文件时必须包含这行
5. **mmdc 路径** — Windows 上用 `npx.cmd` 而非 `mmdc`，加 `shell=True`
6. **终端编码** — `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` 防止 GBK 报错
7. **classDiagram 的 `{}` 不是错误** — classDiagram 用 `{}` 定义类成员跨多行是合法的，flowchart 规则不应误报
8. **`]` 在续行开头** — 合并多行时，续行用 `lstrip()` 去缩进，不能用 `rstrip()`（会删掉 `]`）
9. **引号标签内的裸引号** — `["near[i"]~far[i]"]` 中内层 `"` 关闭外层引号，必须去掉内层引号
10. **`<br/>` 替换为 `\n` 时保留反斜杠** — `\\n` 是字面量 `\n`（反斜杠+n），不是真正的换行符
11. **sequenceDiagram 也要检测** — 脚本不能只处理 flowchart，所有 mermaid 类型都要扫描
12. **`<br>` 和 `<br/>` 都要处理** — 不要漏掉不带 `/` 的变体
13. **sequenceDiagram participant别名不要与消息内容冲突** — `participant Actor as KG3D_Actor` + `Engine->>Actor: new KG3D_Actor()` 会导致mmdc把消息中的 `KG3D_Actor` 当作participant引用，报 `participant_actor` 错误。解决：改别名如 `participant Ac as KG3D_Actor`
14. **sequenceDiagram的 `Note over` 必须单行** — 多行文本会导致 `got 'NEWLINE'` 错误。解决：合并为单行，用 `\n` 连接，外层加引号：`Note over X: "line1\nline2"`
