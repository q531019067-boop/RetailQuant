# Mermaid 规则参考

## 11 条检测规则

| # | 模式 | 错误 | 修复 | 适用范围 |
|---|------|------|------|----------|
| R1 | `<br/>` | HTML标签不被mermaid支持 | → `\n` | 所有类型 |
| R2 | 跨行 `[内容` 换行 `]` | 节点标签跨行 | 合并为一行 `\n` 连接 | flowchart |
| R3 | `{内容` 换行 `}` | 菱形节点跨行 | → `{内容\n内容}` | flowchart |
| R4 | `[K::F()]` `[/]` | 特殊字符裸露 | → `["K::F()"]` | flowchart |
| R5 | `["m_arr[col]"]` | 引号内嵌 `[]` | → `["m_arr(col)"]` | flowchart |
| R6 | `[Get("x")]` | 裸引号 | → `["Get('x')"]` | flowchart |
| R7 | `["'text'"]` | 嵌套引号 | → `["text"]` | 所有类型 |
| R8 | 孤立 `flowchart TD` | 缺 `` ```mermaid `` 前缀 | 补上 | — |
| R9 | `]``` ` 紧贴 | 关闭符不在独立行 | 换行分隔 | 所有类型 |
| R10 | mmdc 权威验证 | 任何解析错误 | 逐一修复 | 所有类型 |
| R11 | `["text "inner" text"]` | 引号标签内含裸引号 | → `["text 'inner' text"]` | 所有类型 |
| R12 | `A->>B: func()` | sequenceDiagram消息含()` | → `A->>B: "func()"` | sequenceDiagram |
| R13 | `Note over X:` 跨行 | sequenceDiagram Note多行 | 合并为单行 `\n` | sequenceDiagram |

## 修复顺序

按此顺序处理，后面的修复可能依赖前面的结果：
1. `"'...'"` → 清除外层单引号
2. `]``` ` → 插入换行
3. `<br/>` → `\n`
4. 跨行节点 → 合并（仅 flowchart）
5. 特殊字符 → 加引号（仅 flowchart）
6. `[]` 嵌套 → `()`（仅 flowchart）
7. `["...text"..."]` → 引号标签内裸引号替换为单引号
8. mmdc 验证 → 手动修复剩余

## 特殊字符清单

标签内含以下字符必须加引号：
`( ) < > : = [ ] { } /`
