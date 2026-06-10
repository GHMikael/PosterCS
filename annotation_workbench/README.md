# Audit v2 Annotation Workbench

本目录是独立的人工标注小工具，默认写回：

`../datasets/gold/audit_v2_labels_annotatorA.csv`

它不会改主项目代码。第一次保存前会在同目录生成一份备份，例如：

`audit_v2_labels_annotatorA.csv.bak-20260611-103000`

## 启动

```bash
cd /Users/mikaelsnow/Documents/ECNU/Paper_Comment_Poster/PosterCS
python annotation_workbench/server.py
```

然后打开：

`http://127.0.0.1:8765`

如果 8765 被占用，可以换端口：

```bash
python annotation_workbench/server.py --port 8766
```

## 使用

- 左侧显示当前 `iter1_png`。
- 右侧填写 `free_notes`、`primary_issue`、`secondary_issues`、`other_description`、`guard_notes`、`confidence`。
- 点 `保存并下一张` 会写回 CSV 并跳到下一条未完成记录。
- `Cmd+Enter` 或 `Ctrl+Enter` 也会保存并下一张。
- `Alt+Left` / `Alt+Right` 可以切换上一张 / 下一张。

## 保存校验

工具会阻止这些明显不合规的保存：

- `free_notes` 为空。
- `confidence` 不是 0 到 1 的数字。
- `secondary_issues` 选择了 `none`。
- `secondary_issues` 重复了 `primary_issue`。
- 选择了 `other` 但没有填写 `other_description`。
- `primary_issue=none` 时还选择了 secondary。

## 测试

```bash
python -m unittest annotation_workbench/test_server.py -v
```
