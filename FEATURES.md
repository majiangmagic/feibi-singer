# FEATURES.md

## 功能清单规则
- 同一时间只激活一个 `in_progress` 功能。
- 只有三层验证全部通过才能标记 `passing`。

## F001：可验证的 dry-run 流水线骨架
- 优先级：1
- 状态：`passing`
- 验证证据：`pytest -q` 输出 4 passed；CLI dry-run 输出 `all_passed: true`。

## F002：真实音频分离和多语言 ASR 接入
- 优先级：2
- 状态：`not_started`

## F003：ACE-Step 1.5 歌词修改接入
- 优先级：2
- 状态：`not_started`

## F004：RVC 菲比音色转换接入
- 优先级：2
- 状态：`not_started`
